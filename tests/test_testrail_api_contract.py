"""TestRail の一次仕様に基づく API 契約と、取り込み中断時の出力契約。

仕様確認日: 2026-09-12。期待値は製品コードの定数から生成しない。
https://support.testrail.com/hc/en-us/articles/7077935129364-Statuses
https://support.testrail.com/hc/en-us/articles/7077990441108-Tests
https://support.testrail.com/hc/en-us/articles/7077819312404-Results

取得失敗時の fail-closed はこの取り込みツールの契約であり、TestRail
自体の動作仕様ではない。既存の配列応答も後方互換として受け入れる。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from bb_harness.tools import import_testrail as importer

BASE_URL = "https://example.testrail.io"
HEADERS = {"Content-Type": "application/json"}
AUTH = ("qa@example.invalid", "dummy-api-key")


def response(payload: object) -> Mock:
    result = Mock()
    result.json.return_value = payload
    return result


def page(key: str, items: list[dict], *, offset: int = 0, next_link=None) -> dict:
    return {
        "offset": offset,
        "limit": 250,
        "size": len(items),
        "_links": {"next": next_link, "prev": None},
        key: items,
    }


@pytest.fixture
def requests_mock(monkeypatch: pytest.MonkeyPatch) -> Mock:
    client = Mock()
    monkeypatch.setattr(importer, "lazy_import_requests", lambda: client)
    monkeypatch.setenv("TESTRAIL_URL", BASE_URL)
    monkeypatch.setenv("TESTRAIL_USER", AUTH[0])
    monkeypatch.setenv("TESTRAIL_API_KEY", AUTH[1])
    return client


@pytest.mark.parametrize(
    ("status_id", "expected"),
    [(1, "pass"), (2, "blocked"), (3, "skip"), (4, "skip"), (5, "fail")],
    ids=["passed", "blocked", "untested", "retest", "failed"],
)
def test_official_status_ids_are_converted(status_id: int, expected: str) -> None:
    evidence = importer.convert_to_execution_evidence(
        {"id": 101, "case_id": 7, "status_id": status_id},
        {"status_id": status_id, "defects": "BUG-42"},
        "QA 担当者",
        17,
    )

    assert evidence["result"] == expected
    if status_id == 5:
        assert evidence["defect_stub"]["title"] == "Defect BUG-42"
        assert evidence["defect_stub"]["status"] == "open"


def test_get_tests_unwraps_official_envelope(requests_mock: Mock) -> None:
    tests = [{"id": 101, "case_id": 7, "source_case_id": "TC-007", "status_id": 5}]
    requests_mock.get.return_value = response(page("tests", tests))

    assert importer.fetch_tests(BASE_URL, HEADERS, AUTH, 17) == tests


def test_get_tests_follows_all_next_pages(requests_mock: Mock) -> None:
    first = {"id": 101, "case_id": 7, "status_id": 1}
    second = {"id": 102, "case_id": 8, "status_id": 5}
    requests_mock.get.side_effect = [
        response(
            page(
                "tests", [first],
                next_link="/api/v2/get_tests/17&limit=250&offset=250",
            )
        ),
        response(page("tests", [second], offset=250)),
    ]

    assert importer.fetch_tests(BASE_URL, HEADERS, AUTH, 17) == [first, second]
    assert requests_mock.get.call_count == 2
    assert requests_mock.get.call_args_list[1].args[0] == (
        f"{BASE_URL}/index.php?/api/v2/get_tests/17&limit=250&offset=250"
    )
    assert requests_mock.get.call_args_list[1].kwargs["auth"] == AUTH


@pytest.mark.parametrize(
    "next_link",
    [
        "https://unrelated.invalid/api/v2/get_tests/17&offset=250",
        "/api/v2/get_tests/99&offset=250",
    ],
    ids=["different-origin", "different-run"],
)
def test_get_tests_rejects_next_outside_requested_api(
    requests_mock: Mock, next_link: str
) -> None:
    requests_mock.get.return_value = response(
        page("tests", [{"id": 101}], next_link=next_link)
    )

    with pytest.raises(ValueError):
        importer.fetch_tests(BASE_URL, HEADERS, AUTH, 17)

    # 不正な次ページに認証情報を付けたリクエストを送らない。
    assert requests_mock.get.call_count == 1


def test_get_results_unwraps_latest_result(requests_mock: Mock) -> None:
    latest = {"id": 902, "test_id": 101, "status_id": 5, "defects": "BUG-42"}
    older = {"id": 901, "test_id": 101, "status_id": 1}
    requests_mock.get.return_value = response(page("results", [latest, older]))

    assert importer.fetch_test_results(BASE_URL, HEADERS, AUTH, 101) == latest


def test_get_tests_rejects_cyclic_next_without_repeating_requests(
    requests_mock: Mock,
) -> None:
    next_link = "/api/v2/get_tests/17&limit=250&offset=250"
    requests_mock.get.side_effect = [
        response(page("tests", [{"id": 101}], next_link=next_link)),
        response(page("tests", [{"id": 102}], offset=250, next_link=next_link)),
        # 循環を見落とした実装でも、3 回目で必ず終了させる。
        AssertionError("同じページに再リクエストした"),
    ]

    with pytest.raises(ValueError):
        importer.fetch_tests(BASE_URL, HEADERS, AUTH, 17)

    assert requests_mock.get.call_count == 2


def test_get_results_accepts_empty_official_page(requests_mock: Mock) -> None:
    requests_mock.get.return_value = response(page("results", []))

    assert importer.fetch_test_results(BASE_URL, HEADERS, AUTH, 101) == {}


def test_legacy_test_array_remains_supported(requests_mock: Mock) -> None:
    tests = [{"id": 101, "case_id": 7, "source_case_id": "TC-007", "status_id": 5}]
    requests_mock.get.return_value = response(tests)

    assert importer.fetch_tests(BASE_URL, HEADERS, AUTH, 17) == tests


@pytest.mark.parametrize("results", [[], [{"id": 902, "status_id": 5}]])
def test_legacy_result_array_remains_supported(
    requests_mock: Mock, results: list[dict]
) -> None:
    requests_mock.get.return_value = response(results)

    expected = {} if not results else {"id": 902, "status_id": 5}
    assert importer.fetch_test_results(BASE_URL, HEADERS, AUTH, 101) == expected


def test_import_preserves_failed_and_retest_counts(requests_mock: Mock) -> None:
    requests_mock.get.side_effect = [
        response(
            page(
                "tests",
                [
                    {"id": 101, "case_id": 7, "source_case_id": "TC-007", "status_id": 5},
                    {"id": 102, "case_id": 8, "source_case_id": "TC-008", "status_id": 4},
                ],
            )
        ),
        response(page("results", [{"id": 901, "status_id": 5, "defects": "BUG-42"}])),
        response(page("results", [{"id": 902, "status_id": 4}])),
    ]

    evidence, stats = importer.import_testrail_results(12, 17)

    assert [item["result"] for item in evidence] == ["fail", "skip"]
    assert evidence[0]["defect_stub"]["status"] == "open"
    assert stats["imported_count"] == 2
    assert stats["fail_count"] == 1
    assert stats["skip_count"] == 1
    assert stats["pass_count"] == 0


@pytest.mark.parametrize("failure", ["http", "invalid-json", "invalid-envelope"])
def test_result_retrieval_failure_aborts_without_writing_partial_evidence(
    requests_mock: Mock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: str,
) -> None:
    # 1 件目の成功後に失敗させ、途中までの成功証跡も公開しないことを確認する。
    broken = response({"unexpected": []})
    if failure == "http":
        broken.raise_for_status.side_effect = RuntimeError("HTTP 503")
    elif failure == "invalid-json":
        broken.json.side_effect = ValueError("invalid JSON")
    requests_mock.get.side_effect = [
        response(
            [
                {"id": 101, "case_id": 7, "status_id": 1},
                {"id": 102, "case_id": 8, "status_id": 1},
            ]
        ),
        response([{"id": 901, "status_id": 1}]),
        broken,
    ]
    output = tmp_path / "execution-evidence"
    write_files = Mock(wraps=importer.write_evidence_files)
    monkeypatch.setattr(importer, "write_evidence_files", write_files)
    monkeypatch.setattr(
        "sys.argv",
        [
            "import-testrail", "--project", "12", "--run", "17",
            "--feature-id", "CHECKOUT", "--output", str(output),
        ],
    )

    exit_code = importer.main()

    assert exit_code == 1
    write_files.assert_not_called()
    assert not output.exists()


def test_second_test_page_failure_preserves_existing_output(
    requests_mock: Mock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    broken_page = response({"error": "temporarily unavailable"})
    broken_page.raise_for_status.side_effect = RuntimeError("HTTP 503")
    requests_mock.get.side_effect = [
        response(
            page(
                "tests",
                [{"id": 101, "case_id": 7, "status_id": 1}],
                next_link="/api/v2/get_tests/17&limit=250&offset=250",
            )
        ),
        broken_page,
    ]
    output = tmp_path / "execution-evidence"
    output.mkdir()
    existing = output / "evidence-before-import.json"
    original_bytes = b'{"result":"fail","anomaly_notes":["existing evidence"]}\n'
    existing.write_bytes(original_bytes)
    write_files = Mock(wraps=importer.write_evidence_files)
    monkeypatch.setattr(importer, "write_evidence_files", write_files)
    monkeypatch.setattr(
        "sys.argv",
        [
            "import-testrail", "--project", "12", "--run", "17",
            "--feature-id", "CHECKOUT", "--output", str(output),
        ],
    )

    exit_code = importer.main()

    assert exit_code == 1
    write_files.assert_not_called()
    assert list(output.iterdir()) == [existing]
    assert existing.read_bytes() == original_bytes
    # envelope で即座に失敗しただけの実装を成功扱いしない。
    broken_page.raise_for_status.assert_called_once()
    assert requests_mock.get.call_count == 2
    assert requests_mock.get.call_args_list[1].args[0] == (
        f"{BASE_URL}/index.php?/api/v2/get_tests/17&limit=250&offset=250"
    )
