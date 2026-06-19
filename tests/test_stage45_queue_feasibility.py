from scripts.classify_phase45_unfinished_multimodal_queues import (
    isolate_known_failures,
    read_document_ids_files,
    split_three_queues,
)
from scripts.probe_phase45_vision_provider import sanitize_probe_error


def test_split_three_queues_distributes_ids_stably() -> None:
    queues = split_three_queues([10, 11, 12, 13, 14, 15, 16])

    assert queues["official_a"] == [10, 13, 16]
    assert queues["official_b"] == [11, 14]
    assert queues["paratera_c"] == [12, 15]


def test_isolate_known_failures_removes_only_when_enabled() -> None:
    document_ids = [10, 11, 12, 13]
    known_failures = {11, 13}

    assert isolate_known_failures(document_ids, known_failures, enabled=True) == [10, 12]
    assert isolate_known_failures(document_ids, known_failures, enabled=False) == document_ids


def test_read_document_ids_files_ignores_missing_and_blank_lines(tmp_path) -> None:
    ids_path = tmp_path / "processed_document_ids.txt"
    ids_path.write_text("10\n\n 11 \n", encoding="utf-8")

    assert read_document_ids_files([ids_path, tmp_path / "missing.txt"]) == {10, 11}


def test_partial_ids_can_be_read_separately_from_processed_ids(tmp_path) -> None:
    processed_path = tmp_path / "processed_document_ids.txt"
    partial_path = tmp_path / "partial_document_ids.txt"
    processed_path.write_text("10\n", encoding="utf-8")
    partial_path.write_text("11\n", encoding="utf-8")

    assert read_document_ids_files([processed_path]) == {10}
    assert read_document_ids_files([partial_path]) == {11}


def test_sanitize_probe_error_collapses_timeout() -> None:
    error = RuntimeError("[WinError 10060] connection failed")

    assert sanitize_probe_error(error) == "RuntimeError: provider_timeout"
