"""OpenAI互換ローカルランタイムの安全性テスト。"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from bb_harness.local_runtime import (
    LocalRuntimeConfig,
    LocalRuntimeError,
    OpenAICompatibleClient,
    _parse_json_object,
    resolve_config,
)


def test_resolve_config_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BB_HARNESS_LOCAL_BASE_URL", "http://127.0.0.1:9000/v1")
    monkeypatch.setenv("BB_HARNESS_LOCAL_MODEL", "env-model")
    config = resolve_config(
        "generic",
        base_url="http://127.0.0.1:9100/v1",
        model="cli-model",
    )
    assert config.base_url == "http://127.0.0.1:9100/v1"
    assert config.model == "cli-model"


def test_non_loopback_is_rejected_by_default() -> None:
    with pytest.raises(LocalRuntimeError, match="Non-loopback"):
        resolve_config("generic", base_url="http://example.test/v1")


def test_non_loopback_requires_explicit_opt_in() -> None:
    config = resolve_config(
        "generic",
        base_url="http://trusted.example.test/v1",
        allow_non_loopback=True,
    )
    assert config.base_url == "http://trusted.example.test/v1"


def _client(model: str | None = None) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        LocalRuntimeConfig(
            profile="test",
            base_url="http://127.0.0.1:9999/v1",
            model=model,
            timeout_seconds=1,
            temperature=0.1,
            max_tokens=100,
        )
    )


@pytest.mark.parametrize("models", [[], [{"id": "a"}, {"id": "b"}]])
def test_model_discovery_rejects_zero_or_multiple(
    monkeypatch: pytest.MonkeyPatch, models: list[dict[str, str]]
) -> None:
    client = _client()
    monkeypatch.setattr(client, "_request", lambda *_: {"data": models})
    with pytest.raises(LocalRuntimeError, match="candidates"):
        client.discover_model()


def test_model_discovery_accepts_exactly_one(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    monkeypatch.setattr(client, "_request", lambda *_: {"data": [{"id": "only"}]})
    assert client.discover_model() == "only"


def test_connection_error_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client("loaded")

    def fail(*_: object, **__: object) -> None:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(LocalRuntimeError, match="connection failed"):
        client._request("GET", "/models")


def test_timeout_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client("loaded")

    def fail(*_: object, **__: object) -> None:
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(LocalRuntimeError, match="connection failed"):
        client._request("GET", "/models")


def test_http_error_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client("loaded")

    def fail(*_: object, **__: object) -> None:
        raise urllib.error.HTTPError(
            "http://127.0.0.1",
            500,
            "failure",
            {},
            io.BytesIO(b'{"error":"boom"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(LocalRuntimeError, match="HTTP 500"):
        client._request("GET", "/models")


def test_invalid_json_and_empty_content_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client("loaded")
    monkeypatch.setattr(
        client,
        "_request",
        lambda *_args, **_kwargs: {"choices": [{"message": {"content": ""}}]},
    )
    with pytest.raises(LocalRuntimeError, match="does not contain"):
        client.complete_json(system="s", user="u", schema_name="x", schema={"type": "object"})
    with pytest.raises(LocalRuntimeError, match="invalid JSON"):
        _parse_json_object("not-json {broken}")


def test_stage_override_is_applied_without_recording_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = LocalRuntimeConfig(
        profile="test",
        base_url="http://127.0.0.1:9999/v1",
        model="loaded",
        timeout_seconds=1,
        temperature=0.2,
        max_tokens=100,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        stage_overrides={
            "test_model": {
                "temperature": 0.05,
                "max_tokens": 321,
                "extra_body": {"chat_template_kwargs": {"enable_thinking": True}},
            }
        },
    )
    client = OpenAICompatibleClient(config)
    captured: dict[str, object] = {}

    def respond(_method: str, _path: str, body: dict[str, object]) -> dict[str, object]:
        captured.update(body)
        return {
            "model": "loaded",
            "choices": [{"message": {"content": json.dumps({"ok": True})}}],
        }

    monkeypatch.setattr(client, "_request", respond)
    client.complete_json(
        system="secret-system",
        user="secret-user",
        schema_name="test_model",
        schema={"type": "object"},
    )
    assert captured["temperature"] == 0.05
    assert captured["max_tokens"] == 321
    assert captured["chat_template_kwargs"] == {"enable_thinking": True}
