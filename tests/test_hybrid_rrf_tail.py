from dataclasses import replace

from app.services.retrieval.hybrid_rrf_tail import HybridRrfTailSearchService
from app.services.retrieval.hybrid_search import HybridSearchResult
from app.services.retrieval.rrf_fusion import RRFHybridSearchResult


def test_hybrid_rrf_tail_preserves_hybrid_head_and_fills_tail() -> None:
    hybrid = FakeSearchService(
        [
            make_hybrid_result(1, "hybrid head 1"),
            make_hybrid_result(2, "hybrid head 2"),
            make_hybrid_result(3, "hybrid head 3"),
            make_hybrid_result(4, "hybrid tail 4"),
            make_hybrid_result(5, "hybrid tail 5"),
        ]
    )
    rrf = FakeSearchService(
        [
            make_rrf_result(3, "duplicate rrf head"),
            make_rrf_result(9, "rrf rescue 9"),
            make_rrf_result(10, "rrf rescue 10"),
        ]
    )

    results = HybridRrfTailSearchService(
        db=None,
        embedding_provider=object(),
        stable_head_k=3,
        hybrid_service=hybrid,
        rrf_service=rrf,
    ).search("invented rock-filled concrete", top_k=5)

    assert [result.chunk_id for result in results] == [1, 2, 3, 9, 10]
    assert results[0].document_title == "hybrid head 1"
    assert results[3].document_title == "rrf rescue 9"


def test_hybrid_rrf_tail_rejects_invalid_head_size() -> None:
    try:
        HybridRrfTailSearchService(db=None, embedding_provider=object(), stable_head_k=0)
    except ValueError as exc:
        assert "stable_head_k" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid stable_head_k")


class FakeSearchService:
    def __init__(self, results):
        self.results = results

    def search(self, query: str, top_k: int = 5):
        return self.results[:top_k]


def make_hybrid_result(chunk_id: int, title: str) -> HybridSearchResult:
    return HybridSearchResult(
        document_id=chunk_id,
        document_title=title,
        source_type="web_page",
        source_path=None,
        file_name=f"{chunk_id}.md",
        chunk_id=chunk_id,
        chunk_index=0,
        content=title,
        heading_path=None,
        score=1.0,
        keyword_score=1.0,
        vector_score=0.0,
    )


def make_rrf_result(chunk_id: int, title: str) -> RRFHybridSearchResult:
    base = RRFHybridSearchResult(
        document_id=chunk_id,
        document_title=title,
        source_type="web_page",
        source_path=None,
        file_name=f"{chunk_id}.md",
        chunk_id=chunk_id,
        chunk_index=0,
        content=title,
        heading_path=None,
        score=1.0,
        bm25_score=1.0,
        vector_score=0.0,
        bm25_rank=1,
        vector_rank=None,
        rrf_score=1.0,
        matched_channels=("bm25",),
        provenance="test",
    )
    return replace(base, core_content=title)
