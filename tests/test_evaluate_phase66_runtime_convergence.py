import time
from pathlib import Path

import pytest

from scripts.evaluate_phase66_runtime_convergence import (
    Phase66ManifestInputs,
    Phase66HttpCase,
    build_manifest,
    collect_http_observations,
    collect_results,
    contract_violations_for_observation,
    load_receipt,
    merge_results,
    validate_only,
)


PATCH_SHA = "a" * 64


def valid_inputs(**overrides: object) -> Phase66ManifestInputs:
    values = {
        "a_identity": "be23e215:empty",
        "b_identity": f"be23e215:patch:{PATCH_SHA}",
        "b_patch_sha256": PATCH_SHA,
        "baseline_contract": Path("output/phase66/baseline/agent-contract.json"),
    }
    values.update(overrides)
    return Phase66ManifestInputs(**values)


def test_manifest_requires_fresh_phase66_cases() -> None:
    manifest = build_manifest(valid_inputs())

    assert manifest.phase == 66
    assert manifest.text_case_count == 30
    assert manifest.image_case_count >= 4
    assert manifest.repetitions == 1
    assert manifest.semantic_cache_enabled is False
    assert manifest.tool_result_cache_enabled is False


def test_manifest_rejects_same_code_identity_for_a_and_b() -> None:
    with pytest.raises(ValueError, match="distinct code identities"):
        build_manifest(valid_inputs(a_identity="same", b_identity="same"))


def test_phase65_result_paths_cannot_satisfy_phase66_gate() -> None:
    with pytest.raises(ValueError, match="phase 66 evidence"):
        load_receipt(Path("output/phase65/summary.json"))


def test_validate_only_writes_review_required_packet(tmp_path: Path) -> None:
    baseline = tmp_path / "agent-contract.json"
    baseline.write_text('{"phase":66,"git_head":"be23e215"}', encoding="utf-8")
    output_root = tmp_path / "evaluation"

    summary = validate_only(
        baseline=baseline,
        output_root=output_root,
        b_patch_sha256=PATCH_SHA,
    )

    assert summary["phase"] == 66
    assert summary["status"] == "review_required"
    assert summary["required_text_cases"] == 30
    assert summary["required_image_cases"] >= 4
    assert "collect_a_command" in summary
    assert "collect_b_command" in summary
    assert "--observations" in str(summary["collect_a_command"])
    assert "--observations" in str(summary["collect_b_command"])
    assert "--collect-http" in str(summary["collect_http_a_command"])
    assert "--collect-http" in str(summary["collect_http_b_command"])
    assert (output_root / "manifest.json").is_file()
    assert (output_root / "summary.json").is_file()
    assert (output_root / "review-packet.md").is_file()


def complete_observations(*, overall: float = 0.8) -> dict[str, object]:
    observations: list[dict[str, object]] = []
    for index in range(1, 31):
        observations.append(
            {
                "case_id": f"phase66_text_{index:02d}",
                "modality": "text",
                "ok": True,
                "error_category": "",
                "completion_score": 1.0,
                "answer_accuracy_score": overall,
                "citation_correctness_score": overall,
                "overall_score": overall,
                "elapsed_ms": 1000.0,
                "observed_tool_names": "hybrid_search_knowledge",
            }
        )
    for index in range(1, 5):
        observations.append(
            {
                "case_id": f"phase66_image_{index:02d}",
                "modality": "image",
                "ok": True,
                "error_category": "",
                "completion_score": 1.0,
                "answer_accuracy_score": overall,
                "citation_correctness_score": overall,
                "overall_score": overall,
                "elapsed_ms": 1000.0,
                "observed_tool_names": "hybrid_search_knowledge",
            }
        )
    return {"phase": 66, "observations": observations}


def test_collect_results_writes_phase66_summary_from_observation_receipt(tmp_path: Path) -> None:
    observations_path = tmp_path / "observations.json"
    observations_path.write_text(
        '{"phase":66,"observations":[]}',
        encoding="utf-8",
    )

    summary = collect_results(
        variant="a",
        observations=observations_path,
        output_root=tmp_path / "a",
    )

    assert summary["phase"] == 66
    assert summary["variant"] == "a"
    assert summary["status"] == "review_required"
    assert summary["reason"] == "incomplete_phase66_observation_coverage"
    assert (tmp_path / "a" / "summary.json").is_file()


def test_collect_results_summarizes_complete_observations(tmp_path: Path) -> None:
    observations_path = tmp_path / "observations.json"
    observations_path.write_text(
        __import__("json").dumps(complete_observations(overall=0.81)),
        encoding="utf-8",
    )

    summary = collect_results(
        variant="b",
        observations=observations_path,
        output_root=tmp_path / "b",
    )

    assert summary["status"] == "collected"
    assert summary["text_case_count"] == 30
    assert summary["image_case_count"] == 4
    assert summary["unknown_error_count"] == 0
    assert summary["overall_score"] == pytest.approx(0.81)
    assert summary["elapsed_ms_p50"] == pytest.approx(1000.0)
    assert summary["elapsed_ms_p95"] == pytest.approx(1000.0)


def test_merge_requires_complete_phase66_pairing(tmp_path: Path) -> None:
    a_root = tmp_path / "a"
    b_root = tmp_path / "b"
    observation_path = tmp_path / "complete.json"
    observation_path.write_text(
        __import__("json").dumps(complete_observations(overall=0.8)),
        encoding="utf-8",
    )
    collect_results(variant="a", observations=observation_path, output_root=a_root)

    incomplete = complete_observations(overall=0.9)
    incomplete["observations"] = incomplete["observations"][:-1]
    incomplete_path = tmp_path / "incomplete.json"
    incomplete_path.write_text(__import__("json").dumps(incomplete), encoding="utf-8")
    collect_results(variant="b", observations=incomplete_path, output_root=b_root)

    summary = merge_results(a_results=a_root, b_results=b_root, output_root=tmp_path / "merged")

    assert summary["status"] == "review_required"
    assert summary["reason"] == "incomplete_phase66_pairing"
    assert summary["paired_text_cases"] == 30
    assert summary["paired_image_cases"] == 3


def test_merge_passes_when_complete_b_metrics_do_not_regress(tmp_path: Path) -> None:
    a_root = tmp_path / "a"
    b_root = tmp_path / "b"
    a_path = tmp_path / "a-observations.json"
    b_path = tmp_path / "b-observations.json"
    a_path.write_text(__import__("json").dumps(complete_observations(overall=0.8)), encoding="utf-8")
    b_path.write_text(__import__("json").dumps(complete_observations(overall=0.82)), encoding="utf-8")
    collect_results(variant="a", observations=a_path, output_root=a_root)
    collect_results(variant="b", observations=b_path, output_root=b_root)

    summary = merge_results(a_results=a_root, b_results=b_root, output_root=tmp_path / "merged")

    assert summary["status"] == "passed"
    assert summary["paired_text_cases"] == 30
    assert summary["paired_image_cases"] == 4


def test_merge_fails_when_candidate_latency_p95_regresses(tmp_path: Path) -> None:
    a_root = tmp_path / "a"
    b_root = tmp_path / "b"
    a_path = tmp_path / "a-observations.json"
    b_path = tmp_path / "b-observations.json"
    a_observations = complete_observations(overall=0.8)
    b_observations = complete_observations(overall=0.82)
    for row in a_observations["observations"]:
        row["elapsed_ms"] = 1000.0
    for row in b_observations["observations"]:
        row["elapsed_ms"] = 1600.0
    a_path.write_text(__import__("json").dumps(a_observations), encoding="utf-8")
    b_path.write_text(__import__("json").dumps(b_observations), encoding="utf-8")
    collect_results(variant="a", observations=a_path, output_root=a_root)
    collect_results(variant="b", observations=b_path, output_root=b_root)

    summary = merge_results(a_results=a_root, b_results=b_root, output_root=tmp_path / "merged")

    assert summary["status"] == "failed"
    assert summary["reason"] == "candidate_latency_regressed"
    assert summary["a_elapsed_ms_p95"] == pytest.approx(1000.0)
    assert summary["b_elapsed_ms_p95"] == pytest.approx(1600.0)


def test_merge_fails_when_candidate_figure_latency_p95_regresses(tmp_path: Path) -> None:
    a_root = tmp_path / "a"
    b_root = tmp_path / "b"
    a_path = tmp_path / "a-observations.json"
    b_path = tmp_path / "b-observations.json"
    a_observations = complete_observations(overall=0.8)
    b_observations = complete_observations(overall=0.82)
    for row in a_observations["observations"]:
        row["elapsed_ms"] = 1000.0
    for row in b_observations["observations"]:
        row["elapsed_ms"] = 1000.0
    for payload, elapsed in ((a_observations, 2000.0), (b_observations, 3500.0)):
        for row in payload["observations"][:3]:
            row["observed_tool_names"] = "search_figures|hybrid_search_knowledge"
            row["elapsed_ms"] = elapsed
    a_path.write_text(__import__("json").dumps(a_observations), encoding="utf-8")
    b_path.write_text(__import__("json").dumps(b_observations), encoding="utf-8")
    collect_results(variant="a", observations=a_path, output_root=a_root)
    collect_results(variant="b", observations=b_path, output_root=b_root)

    summary = merge_results(a_results=a_root, b_results=b_root, output_root=tmp_path / "merged")

    assert summary["status"] == "failed"
    assert summary["reason"] == "candidate_figure_latency_regressed"
    assert summary["a_figure_elapsed_ms_p95"] == pytest.approx(2000.0)
    assert summary["b_figure_elapsed_ms_p95"] == pytest.approx(3500.0)


def test_collect_http_observations_writes_safe_receipt_without_answer_text(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    cases.write_text(
        "case_id,modality,question,image_path\n"
        "phase66_text_01,text,What is RFC?,\n"
        "phase66_image_01,image,What is shown?,data/user_uploads/example.png\n",
        encoding="utf-8",
    )

    def fake_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        assert url == "http://127.0.0.1:8001/agent/query"
        assert "question" in payload
        if payload.get("image_path"):
            assert payload["image_path"] == "data/user_uploads/example.png"
        return (
            200,
            {
                "answer": "sensitive generated answer must not be persisted",
                "refused": False,
                "citations": [1],
                "tool_calls": [
                    {
                        "tool_name": "hybrid_search_knowledge",
                        "input_summary": "do not persist",
                        "output_summary": "do not persist",
                    }
                ],
                "sources": [{"content": "source text must not be persisted"}],
            },
        )

    summary = collect_http_observations(
        variant="a",
        base_url="http://127.0.0.1:8001",
        cases_path=cases,
        output_root=tmp_path / "a",
        timeout_seconds=5.0,
        token="",
        post_json=fake_post_json,
    )

    assert summary["phase"] == 66
    assert summary["variant"] == "a"
    assert summary["text_case_count"] == 1
    assert summary["image_case_count"] == 1
    observations_text = (tmp_path / "a" / "observations.json").read_text(encoding="utf-8")
    assert "sensitive generated answer" not in observations_text
    assert "source text" not in observations_text
    assert "do not persist" not in observations_text
    assert "hybrid_search_knowledge" in observations_text


def test_collect_http_observations_elapsed_ms_includes_http_sender_time(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    cases.write_text(
        "case_id,modality,question,image_path\n"
        "phase66_text_01,text,What is RFC?,\n",
        encoding="utf-8",
    )

    def slow_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        time.sleep(0.02)
        return (
            200,
            {
                "answer": "safe answer",
                "refused": False,
                "citations": [],
                "tool_calls": [{"tool_name": "hybrid_search_knowledge"}],
                "sources": [],
            },
        )

    collect_http_observations(
        variant="a",
        base_url="http://127.0.0.1:8001",
        cases_path=cases,
        output_root=tmp_path / "a",
        timeout_seconds=5.0,
        token="",
        post_json=slow_post_json,
    )

    observations = __import__("json").loads((tmp_path / "a" / "observations.json").read_text(encoding="utf-8"))
    assert observations["observations"][0]["elapsed_ms"] >= 15.0


def test_collect_http_observations_can_judge_in_memory_without_persisting_text(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    cases.write_text(
        "case_id,modality,question,image_path\n"
        "phase66_text_01,text,What is RFC?,\n",
        encoding="utf-8",
    )

    def fake_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "answer": "sensitive answer sent to judge only",
                "refused": False,
                "citations": [1],
                "sources": [{"title": "T", "content": "sensitive source sent to judge only"}],
                "tool_calls": [{"tool_name": "hybrid_search_knowledge"}],
            },
        )

    def fake_judge_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        assert url == "http://127.0.0.1:8001/agent/judge"
        assert payload["answer"] == "sensitive answer sent to judge only"
        assert payload["sources"] == [{"title": "T", "content": "sensitive source sent to judge only"}]
        return (
            200,
            {
                "judge_scores": {
                    "faithfulness": 0.9,
                    "answer_coverage": 0.8,
                    "citation_support": 0.7,
                    "refusal_correctness": 1.0,
                    "safety_leak_check": 1.0,
                    "conciseness": 0.6,
                }
            },
        )

    summary = collect_http_observations(
        variant="a",
        base_url="http://127.0.0.1:8001",
        cases_path=cases,
        output_root=tmp_path / "a",
        timeout_seconds=5.0,
        token="",
        post_json=fake_post_json,
        judge=True,
        judge_post_json=fake_judge_post_json,
    )

    assert summary["answer_accuracy_score"] == pytest.approx(0.85)
    assert summary["citation_correctness_score"] == pytest.approx(0.7)
    assert summary["overall_score"] == pytest.approx(0.8333333333)
    observations_text = (tmp_path / "a" / "observations.json").read_text(encoding="utf-8")
    assert "sensitive answer" not in observations_text
    assert "sensitive source" not in observations_text
    assert "answer_accuracy_score" in observations_text


def test_collect_http_observations_trims_judge_payload_to_api_limits(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    cases.write_text(
        "case_id,modality,question,image_path\n"
        "phase66_text_01,text,What is RFC?,\n",
        encoding="utf-8",
    )

    long_answer = "A" * 9000
    long_sources = [
        {"title": f"T{i}", "content": "source text " * 200, "source_type": "text", "chunk_id": i}
        for i in range(20)
    ]

    def fake_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "answer": long_answer,
                "refused": False,
                "citations": list(range(100)),
                "sources": long_sources,
                "tool_calls": [{"tool_name": "hybrid_search_knowledge"}],
            },
        )

    def fake_judge_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        assert len(str(payload["answer"])) <= 8000
        assert len(payload["sources"]) <= 12
        assert all(len(str(source.get("content", ""))) <= 1200 for source in payload["sources"])  # type: ignore[union-attr]
        assert len(payload["citations"]) <= 50
        return (
            200,
            {
                "judge_scores": {
                    "faithfulness": 1.0,
                    "answer_coverage": 1.0,
                    "citation_support": 1.0,
                    "refusal_correctness": 1.0,
                    "safety_leak_check": 1.0,
                    "conciseness": 1.0,
                }
            },
        )

    summary = collect_http_observations(
        variant="a",
        base_url="http://127.0.0.1:8001",
        cases_path=cases,
        output_root=tmp_path / "a",
        timeout_seconds=5.0,
        token="",
        post_json=fake_post_json,
        judge=True,
        judge_post_json=fake_judge_post_json,
    )

    assert summary["judge_failed_count"] == 0
    observations_text = (tmp_path / "a" / "observations.json").read_text(encoding="utf-8")
    assert long_answer not in observations_text
    assert "source text source text" not in observations_text


def test_collect_http_observations_retries_transient_judge_http_failures(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    cases.write_text(
        "case_id,modality,question,image_path\n"
        "phase66_text_01,text,What is RFC?,\n",
        encoding="utf-8",
    )

    def fake_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "answer": "answer",
                "refused": False,
                "citations": [1],
                "sources": [{"title": "T", "content": "source"}],
                "tool_calls": [{"tool_name": "hybrid_search_knowledge"}],
            },
        )

    attempts = {"count": 0}

    def flaky_judge_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return 502, {"detail": "transient"}
        return (
            200,
            {
                "judge_scores": {
                    "faithfulness": 1.0,
                    "answer_coverage": 1.0,
                    "citation_support": 1.0,
                    "refusal_correctness": 1.0,
                    "safety_leak_check": 1.0,
                    "conciseness": 1.0,
                }
            },
        )

    summary = collect_http_observations(
        variant="a",
        base_url="http://127.0.0.1:8001",
        cases_path=cases,
        output_root=tmp_path / "a",
        timeout_seconds=5.0,
        token="",
        post_json=fake_post_json,
        judge=True,
        judge_post_json=flaky_judge_post_json,
    )

    assert attempts["count"] == 2
    assert summary["judge_failed_count"] == 0


def test_collect_http_observations_classifies_http_failures(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    cases.write_text(
        "case_id,modality,question,image_path\n"
        "phase66_text_01,text,What is RFC?,\n",
        encoding="utf-8",
    )

    def fake_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        return 503, {"detail": "unavailable"}

    summary = collect_http_observations(
        variant="b",
        base_url="http://127.0.0.1:8002/",
        cases_path=cases,
        output_root=tmp_path / "b",
        timeout_seconds=5.0,
        token="",
        post_json=fake_post_json,
    )

    assert summary["status"] == "review_required"
    observations = __import__("json").loads((tmp_path / "b" / "observations.json").read_text(encoding="utf-8"))
    assert observations["observations"][0]["ok"] is False
    assert observations["observations"][0]["error_category"] == "http_503"


def test_collect_http_observations_records_connection_errors_per_case(tmp_path: Path) -> None:
    cases = tmp_path / "cases.csv"
    cases.write_text(
        "case_id,modality,question,image_path\n"
        "phase66_text_01,text,What is RFC?,\n",
        encoding="utf-8",
    )

    def fake_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        raise TimeoutError("timed out")

    summary = collect_http_observations(
        variant="a",
        base_url="http://127.0.0.1:8001",
        cases_path=cases,
        output_root=tmp_path / "a",
        timeout_seconds=0.1,
        token="",
        post_json=fake_post_json,
    )

    assert summary["status"] == "review_required"
    observations = __import__("json").loads((tmp_path / "a" / "observations.json").read_text(encoding="utf-8"))
    assert observations["observations"][0]["ok"] is False
    assert observations["observations"][0]["error_category"] == "connection_error"


def test_collect_http_observations_enforces_expected_and_forbidden_tools(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.csv"
    cases_path.write_text(
        "case_id,suite,modality,question,image_path,intent_category,expected_tools,"
        "forbidden_tools,expected_refusal,expected_min_sources,expected_min_citations,"
        "latency_budget_ms,notes\n"
        "case_1,agent_common_v1,text,请展示图片证据。,,pure_figure_lookup,"
        "search_figures,hybrid_search_knowledge,false,1,1,999999,note\n",
        encoding="utf-8",
    )

    def fake_post_json(url: str, payload: dict[str, object], timeout_seconds: float, token: str) -> tuple[int, dict[str, object]]:
        return (
            200,
            {
                "answer": "ok",
                "tool_calls": [
                    {"tool_name": "search_figures"},
                    {"tool_name": "hybrid_search_knowledge"},
                ],
                "sources": [{"id": 1}],
                "citations": [1],
                "refused": False,
            },
        )

    summary = collect_http_observations(
        variant="b",
        base_url="http://127.0.0.1:8000",
        cases_path=cases_path,
        output_root=tmp_path / "out",
        timeout_seconds=1.0,
        token="",
        post_json=fake_post_json,
    )

    assert summary["contract_violation_count"] == 1


def test_contract_violations_detect_refusal_source_citation_and_latency_failures() -> None:
    case = Phase66HttpCase(
        case_id="case_1",
        modality="text",
        question="question",
        expected_tools=("hybrid_search_knowledge",),
        forbidden_tools=("search_figures",),
        expected_refusal=False,
        expected_min_sources=2,
        expected_min_citations=1,
        latency_budget_ms=1000.0,
    )

    violations = contract_violations_for_observation(
        case=case,
        observed_tools=("search_figures",),
        source_count=1,
        citation_count=0,
        refused=True,
        elapsed_ms=1500.0,
    )

    assert violations == (
        "missing_tool:hybrid_search_knowledge",
        "forbidden_tool:search_figures",
        "refusal_mismatch:expected_false",
        "source_floor:1<2",
        "citation_floor:0<1",
        "latency_budget:1500.000>1000.000",
    )


def test_collect_results_marks_complete_but_failed_observations_review_required(tmp_path: Path) -> None:
    observations = complete_observations(overall=0.8)
    rows = observations["observations"]
    assert isinstance(rows, list)
    rows[0]["ok"] = False
    rows[0]["error_category"] = "connection_error"
    observations_path = tmp_path / "observations.json"
    observations_path.write_text(__import__("json").dumps(observations), encoding="utf-8")

    summary = collect_results(
        variant="a",
        observations=observations_path,
        output_root=tmp_path / "a",
    )

    assert summary["status"] == "review_required"
    assert summary["reason"] == "phase66_observations_have_failed_cases"
    assert summary["failed_case_count"] == 1


def test_collect_results_marks_judge_failures_review_required(tmp_path: Path) -> None:
    observations = complete_observations(overall=0.8)
    rows = observations["observations"]
    assert isinstance(rows, list)
    rows[0].pop("answer_accuracy_score", None)
    rows[0].pop("citation_correctness_score", None)
    rows[0].pop("overall_score", None)
    rows[0]["judge_status"] = "failed"
    rows[0]["judge_error_category"] = "http_503"
    observations_path = tmp_path / "observations.json"
    observations_path.write_text(__import__("json").dumps(observations), encoding="utf-8")

    summary = collect_results(
        variant="a",
        observations=observations_path,
        output_root=tmp_path / "a",
    )

    assert summary["status"] == "review_required"
    assert summary["reason"] == "phase66_observations_have_judge_failures"
    assert summary["judge_failed_count"] == 1
