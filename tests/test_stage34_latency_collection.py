from scripts.collect_stage34_latency_traces import primary_bottleneck, safe_value


def test_stage34_latency_collection_classifies_primary_bottleneck() -> None:
    trace = {
        "query_embedding_latency_ms": 10.0,
        "vector_search_latency_ms": 20.0,
        "rerank_latency_ms": 5.0,
        "planner_latency_ms": 7.0,
        "tool_latency_ms": 30.0,
        "answer_latency_ms": 80.0,
    }

    assert primary_bottleneck(trace) == "answer_generation_latency"


def test_stage34_latency_collection_safe_value_never_writes_none() -> None:
    assert safe_value(None) == ""
    assert safe_value(1.23456) == "1.235"
    assert safe_value("faiss_only") == "faiss_only"


def test_stage34_latency_collection_marks_endpoint_total_when_internal_trace_absent() -> None:
    assert primary_bottleneck({"time_to_final_ms": 123.0}) == "endpoint_total_latency"
