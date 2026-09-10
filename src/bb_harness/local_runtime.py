"""OpenAI互換ローカル推論ランタイム。"""

from __future__ import annotations

import ipaddress
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any
from urllib.parse import urlparse

import yaml


class LocalRuntimeError(RuntimeError):
    """ローカル推論の設定・通信・応答が不正な場合。"""

    def __init__(self, message: str, *, usage: dict | None = None, elapsed_seconds: float = 0.0):
        super().__init__(message)
        self.usage = usage or {}
        self.elapsed_seconds = elapsed_seconds
        self.failure_kind = "runtime_error"
        self.finish_reason = None


@dataclass(frozen=True)
class LocalRuntimeConfig:
    """解決済みのローカル推論設定。"""

    profile: str
    base_url: str
    model: str | None
    timeout_seconds: float
    temperature: float
    max_tokens: int
    extra_body: dict[str, Any] = field(default_factory=dict)
    stage_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    api_key: str | None = field(default=None, repr=False)
    generation_mode: str = "compact"
    token_budget: int | None = None


@dataclass(frozen=True)
class CompletionResult:
    """1回のchat completion結果。"""

    value: dict[str, Any]
    elapsed_seconds: float
    usage: dict[str, Any]
    model: str
    finish_reason: str | None = None


def load_profiles() -> dict[str, dict[str, Any]]:
    """同梱profileを読み込む。"""
    resource = files("bb_harness").joinpath("local_profiles.yaml")
    value = yaml.safe_load(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LocalRuntimeError("local_profiles.yaml must contain an object")
    return value


def resolve_config(
    profile: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    timeout_seconds: float | None = None,
    allow_non_loopback: bool = False,
    generation_mode: str = "compact",
    token_budget: int | None = None,
) -> LocalRuntimeConfig:
    """CLI > 環境変数 > profileの順で設定を解決する。"""
    profiles = load_profiles()
    if profile not in profiles:
        raise LocalRuntimeError(f"Unknown local profile: {profile}")
    if generation_mode not in {"compact", "full", "batched"}:
        raise LocalRuntimeError("generation_mode must be compact, full or batched")
    if token_budget is not None and (type(token_budget) is not int or token_budget <= 0):
        raise LocalRuntimeError("token_budget must be a positive integer")
    raw = profiles[profile]
    resolved_url = (
        base_url or os.getenv("BB_HARNESS_LOCAL_BASE_URL") or str(raw.get("base_url", ""))
    ).rstrip("/")
    env_model = os.getenv("BB_HARNESS_LOCAL_MODEL")
    resolved_model = model or env_model or raw.get("model")
    env_timeout = os.getenv("BB_HARNESS_LOCAL_TIMEOUT")
    resolved_timeout = timeout_seconds
    if resolved_timeout is None and env_timeout:
        try:
            resolved_timeout = float(env_timeout)
        except ValueError as exc:
            raise LocalRuntimeError("BB_HARNESS_LOCAL_TIMEOUT must be numeric") from exc
    if resolved_timeout is None:
        resolved_timeout = float(raw.get("timeout_seconds", 240))
    if resolved_timeout <= 0:
        raise LocalRuntimeError("timeout must be greater than zero")
    _validate_endpoint(resolved_url, allow_non_loopback=allow_non_loopback)
    return LocalRuntimeConfig(
        profile=profile,
        base_url=resolved_url,
        model=str(resolved_model) if resolved_model else None,
        timeout_seconds=resolved_timeout,
        temperature=float(raw.get("temperature", 0.2)),
        max_tokens=int(raw.get("max_tokens", 6000)),
        extra_body=dict(raw.get("extra_body") or {}),
        stage_overrides=dict(raw.get("stages") or {}),
        api_key=os.getenv("BB_HARNESS_LOCAL_API_KEY"),
        generation_mode=generation_mode,
        token_budget=token_budget,
    )


def _validate_endpoint(base_url: str, *, allow_non_loopback: bool) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise LocalRuntimeError("base URL must be an absolute http(s) URL")
    if allow_non_loopback:
        return
    host = parsed.hostname.lower()
    if host == "localhost":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise LocalRuntimeError(
        "Non-loopback endpoint rejected; pass --allow-non-loopback only for a trusted server"
    )


class OpenAICompatibleClient:
    """stdlibだけで動作するOpenAI互換client。"""

    def __init__(self, config: LocalRuntimeConfig):
        self.config = config

    def discover_model(self) -> str:
        """model指定がない場合、/modelsに1件だけあるmodelを選ぶ。"""
        if self.config.model:
            return self.config.model
        response = self._request("GET", "/models")
        data = response.get("data")
        ids = [item.get("id") for item in data or [] if isinstance(item, dict)]
        models = [item for item in ids if isinstance(item, str) and item]
        if len(models) != 1:
            raise LocalRuntimeError(
                f"Model is not specified and /models returned {len(models)} candidates"
            )
        return models[0]

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> CompletionResult:
        """JSON Schema制約付きchat completionを行う。"""
        model = self.discover_model()
        stage = schema_name.removesuffix("_repair").split("__", 1)[0]
        stage_config = self.config.stage_overrides.get(stage, {})
        temperature = float(stage_config.get("temperature", self.config.temperature))
        max_tokens = int(stage_config.get("max_tokens", self.config.max_tokens))
        extra_body = dict(self.config.extra_body)
        extra_body.update(dict(stage_config.get("extra_body") or {}))
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name.replace("-", "_")[:64],
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        body.update(extra_body)
        started = time.monotonic()
        try:
            response = self._request("POST", "/chat/completions", body)
        except LocalRuntimeError as exc:
            exc.elapsed_seconds = time.monotonic() - started
            raise
        elapsed = time.monotonic() - started
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        try:
            choice = response["choices"][0]
            reason = choice.get("finish_reason")
            message = choice["message"]
            content = message.get("content")
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LocalRuntimeError(
                "chat completion response has no message content",
                usage=usage,
                elapsed_seconds=elapsed,
            ) from exc
        if reason is not None and reason != "stop":
            exc = LocalRuntimeError(
                f"incomplete model response: finish_reason={str(reason)[:80]}",
                usage=usage,
                elapsed_seconds=elapsed,
            )
            exc.failure_kind = "output_truncated" if reason == "length" else "incomplete_response"
            exc.finish_reason = str(reason)[:80]
            exc.model = str(response.get("model") or model)
            raise exc
        try:
            text = _content_text(content)
        except LocalRuntimeError as exc:
            exc.usage = usage
            exc.elapsed_seconds = elapsed
            exc.finish_reason = reason
            raise
        try:
            value = _parse_json_object(text)
        except LocalRuntimeError as exc:
            exc.usage = usage
            exc.elapsed_seconds = elapsed
            exc.failure_kind = "json_parse_error"
            exc.finish_reason = reason
            raise
        response_model = response.get("model")
        return CompletionResult(
            value=value,
            elapsed_seconds=elapsed,
            usage=usage,
            model=str(response_model or model),
            finish_reason=reason,
        )

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(
            f"{self.config.base_url}{path}",
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise LocalRuntimeError(f"Local API HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LocalRuntimeError(f"Local API connection failed: {exc}") from exc
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LocalRuntimeError("Local API returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise LocalRuntimeError("Local API response must be a JSON object")
        return value


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "".join(parts)
    raise LocalRuntimeError("message content is not text")


def _parse_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise LocalRuntimeError("model output does not contain a JSON object") from None
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LocalRuntimeError(f"model output is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LocalRuntimeError("model output must be a JSON object")
    return value
