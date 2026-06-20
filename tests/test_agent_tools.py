from sqlalchemy.orm import Session, sessionmaker
from PIL import Image

from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    DocumentCreate,
    DocumentRepository,
    SourceCreate,
    SourceRepository,
)
from app.db.session import create_sqlite_engine
from app.services.agent.tools import AgentToolbox
from app.services.agent.tools import figure_specific_requirement_satisfied
from app.services.agent.tools import query_requests_figure
from app.services.agent.tools import search_item_from_result, sources_from_search_results
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.keyword_search import KeywordSearchResult
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_cache import VectorIndexEntry
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "agent_tools.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_agent_tool_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Filling Capacity Evaluation of Self-Compacting Concrete",
            source_type="local_file",
            source_path="filling.md",
            file_name="filling.md",
            file_extension=".md",
            content_hash="agent-tools-filling-hash",
            raw_path="data/raw/filling.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Filling capacity depends on self-compacting concrete flowability in prepacked rock voids.",
                char_count=88,
                heading_path="Filling",
                start_char=0,
                end_char=88,
            )
        ],
    )


def source_record(**overrides) -> SourceCreate:
    data = {
        "source_id": "rfc_source_001",
        "title": "Filling Capacity Evaluation of Self-Compacting Concrete",
        "normalized_title": "filling capacity evaluation of self-compacting concrete",
        "authors": "Example Author",
        "year": "2014",
        "venue": "Example Journal",
        "category": "filling_capacity",
        "discovered_via": "test",
        "doi": "10.123/example",
        "normalized_doi": "10.123/example",
        "url": "https://example.org/filling",
        "normalized_url": "https://example.org/filling",
        "pdf_url": None,
        "abstract": "A source about filling capacity.",
        "keywords": "rock-filled concrete; filling capacity",
        "language": "en",
        "citation_count": 10,
        "source_type": "metadata_record",
        "trust_level": "high",
        "access_rights": "metadata",
        "fulltext_permission": "metadata_only",
        "license_or_terms": None,
        "local_path": None,
        "status": "collected",
        "notes": "test source",
        "document_id": None,
    }
    data.update(overrides)
    return SourceCreate(**data)


def make_toolbox(db: Session) -> AgentToolbox:
    return AgentToolbox(
        db=db,
        embedding_provider=DeterministicEmbeddingProvider(dimension=32),
        chat_model_provider=DeterministicChatModelProvider(),
        log_answers=False,
    )


class FailingEmbeddingProvider:
    provider_name = "failing-embedding"
    model_name = "failing-embedding-v1"
    dimension = 32

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("Embedding provider unavailable")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding provider unavailable")


def test_agent_toolbox_search_knowledge_returns_keyword_results(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_agent_tool_documents(db)
        result = make_toolbox(db).search_knowledge("filling capacity", top_k=3)

    assert result.tool_name == "search_knowledge"
    assert result.call.succeeded
    assert not result.refused
    assert result.search_results
    assert result.search_results[0].document_title == "Filling Capacity Evaluation of Self-Compacting Concrete"
    assert result.sources[0].source_id.startswith("chunk:")


def test_agent_search_item_preserves_image_caption() -> None:
    search_result = KeywordSearchResult(
        document_id=1,
        document_title="Image source",
        source_type="local_file",
        source_path="image.pdf",
        file_name="image.pdf",
        chunk_id=42,
        chunk_index=3,
        content="Image description.",
        heading_path="Figures",
        score=0.9,
        chunk_type="image_description",
        source_image_path="data/images/1/page2_img3.png",
        caption="Fig. 2 Image caption",
    )

    item = search_item_from_result(search_result)
    source = sources_from_search_results([item])[0]

    assert item.caption == "Fig. 2 Image caption"
    assert item.page_number == 2
    assert source.caption == "Fig. 2 Image caption"
    assert source.page_number == 2


def seed_agent_tool_image_documents(db: Session) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="RFC Figure Source",
            source_type="local_file",
            source_path="figure.pdf",
            file_name="figure.pdf",
            file_extension=".pdf",
            content_hash="agent-tools-figure-hash",
            raw_path="data/raw/figure.pdf",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="stress strain curve of rock-filled concrete compression failure morphology",
                char_count=75,
                heading_path="Figures",
                start_char=None,
                end_char=None,
                chunk_type="image_description",
                source_image_path="data/images/7/page12_img1.png",
                caption="Fig. 6 Compression failure morphology",
            ),
            ChunkCreate(
                chunk_index=1,
                content="stress strain curve duplicate on the same page",
                char_count=44,
                heading_path="Figures",
                start_char=None,
                end_char=None,
                chunk_type="image_description",
                source_image_path="data/images/7/page12_img2.png",
                caption="Fig. 6 Duplicate",
            ),
            ChunkCreate(
                chunk_index=2,
                content="stress strain curve tiny unusable figure",
                char_count=39,
                heading_path="Figures",
                start_char=None,
                end_char=None,
                chunk_type="image_description",
                source_image_path="data/images/7/page13_img1.png",
                caption="Fig. 7 Tiny",
            ),
        ],
    )


def write_test_image(path, *, size=(80, 80)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(120, 120, 120)).save(path)


def test_agent_toolbox_hybrid_search_uses_hybrid_tool_name_and_results(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_agent_tool_documents(db)
        VectorIndexService(db, provider).build_index()
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )

        result = toolbox.hybrid_search_knowledge("filling capacity", top_k=3)

    assert result.tool_name == "hybrid_search_knowledge"
    assert result.call.succeeded
    assert result.search_results
    assert result.sources[0].score is not None


def test_agent_toolbox_hybrid_search_reports_provider_failures(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_agent_tool_documents(db)
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=FailingEmbeddingProvider(),
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )

        result = toolbox.hybrid_search_knowledge("filling capacity", top_k=3)

    assert result.tool_name == "hybrid_search_knowledge"
    assert not result.call.succeeded
    assert result.call.error == "Embedding provider unavailable"
    assert result.refused


def test_agent_toolbox_search_figures_returns_quality_checked_image_results(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_test_image(tmp_path / "data" / "images" / "7" / "page12_img1.png")
    write_test_image(tmp_path / "data" / "images" / "7" / "page12_img2.png")
    write_test_image(tmp_path / "data" / "images" / "7" / "page13_img1.png", size=(20, 20))
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        provider = DeterministicEmbeddingProvider(dimension=32)
        seed_agent_tool_image_documents(db)
        VectorIndexService(db, provider).build_index()
        toolbox = AgentToolbox(
            db=db,
            embedding_provider=provider,
            chat_model_provider=DeterministicChatModelProvider(),
            log_answers=False,
        )

        result = toolbox.search_figures("stress strain curve compression failure morphology", top_k=4)

    assert result.tool_name == "search_figures"
    assert result.call.succeeded
    assert not result.refused
    assert len(result.figure_results) == 1
    figure = result.figure_results[0]
    assert figure.image_url == "/assets/images/7/page12_img1.png"
    assert figure.caption == "Fig. 6 Compression failure morphology"
    assert figure.page_number == 12
    assert figure.document_title == "RFC Figure Source"
    assert figure.relevance_score >= 0.35
    assert result.sources[0].page_number == 12


def test_search_figures_rejects_generic_curve_for_stress_strain_query() -> None:
    generic_curve = VectorIndexEntry(
        chunk_id=1,
        document_id=1,
        document_title="\u7c89\u7164\u7070\u63ba\u91cf\u5bf9\u5806\u77f3\u6df7\u51dd\u571f\u7edd\u70ed\u6e29\u5347\u503c\u5f71\u54cd\u7684\u8bd5\u9a8c\u7814\u7a76",
        source_type="local_file",
        source_path="thermal.pdf",
        file_name="thermal.pdf",
        chunk_index=0,
        content="\u4e09\u79cd\u8ba1\u7b97\u6a21\u578b\u62df\u5408\u66f2\u7ebf\uff0c\u6e29\u5ea6\u5e94\u529b\u4e0e\u6e29\u63a7\u63aa\u65bd\u5206\u6790\u3002",
        heading_path="Figure",
        chunk_type="image_description",
        source_image_path="data/images/1/page35_img1.png",
        caption="\u56fe3-4 \u4e09\u79cd\u8ba1\u7b97\u6a21\u578b\u62df\u5408\u66f2\u7ebf",
        page_number=35,
    )
    stress_strain_curve = VectorIndexEntry(
        chunk_id=2,
        document_id=2,
        document_title="\u5806\u77f3\u6df7\u51dd\u571f\u5c3a\u5bf8\u6548\u5e94\u53ca\u6807\u51c6\u503c\u7814\u7a76",
        source_type="local_file",
        source_path="stress-strain.pdf",
        file_name="stress-strain.pdf",
        chunk_index=0,
        content="\u6807\u51c6\u8bd5\u4ef6 L-150-52 \u5e94\u529b\u5e94\u53d8\u66f2\u7ebf\u56fe\u53ca\u7834\u574f\u7ed3\u679c\u56fe\u3002",
        heading_path="Figure",
        chunk_type="image_description",
        source_image_path="data/images/2/page41_img5.png",
        caption="\u56fe3-4 \u6807\u51c6\u8bd5\u4ef6 L-150-52 \u5e94\u529b\u5e94\u53d8\u66f2\u7ebf\u56fe\u53ca\u7834\u574f\u7ed3\u679c\u56fe",
        page_number=41,
    )

    assert not figure_specific_requirement_satisfied(
        "\u5806\u77f3\u6df7\u51dd\u571f\u7684\u5e94\u529b\u5e94\u53d8\u66f2\u7ebf",
        generic_curve,
    )
    assert figure_specific_requirement_satisfied(
        "\u5806\u77f3\u6df7\u51dd\u571f\u7684\u5e94\u529b\u5e94\u53d8\u66f2\u7ebf",
        stress_strain_curve,
    )
    assert figure_specific_requirement_satisfied(
        "\u5806\u77f3\u6df7\u51dd\u571f\u66f2\u7ebf",
        generic_curve,
    )


def test_search_figures_uses_specific_terms_beyond_single_case() -> None:
    thermal_curve = VectorIndexEntry(
        chunk_id=3,
        document_id=3,
        document_title="thermal control study",
        source_type="local_file",
        source_path="thermal.pdf",
        file_name="thermal.pdf",
        chunk_index=0,
        content="adiabatic temperature rise curve and hydration heat distribution",
        heading_path="Figure",
        chunk_type="image_description",
        source_image_path="data/images/3/page10_img1.png",
        caption="Fig. 3 Adiabatic temperature rise curve",
        page_number=10,
    )
    microstructure_image = VectorIndexEntry(
        chunk_id=4,
        document_id=4,
        document_title="interface microstructure study",
        source_type="local_file",
        source_path="micro.pdf",
        file_name="micro.pdf",
        chunk_index=0,
        content="SEM microstructure image of interface transition zone",
        heading_path="Figure",
        chunk_type="image_description",
        source_image_path="data/images/4/page6_img1.png",
        caption="Fig. 4 Interface microstructure",
        page_number=6,
    )

    assert figure_specific_requirement_satisfied("show hydration heat curve", thermal_curve)
    assert not figure_specific_requirement_satisfied("show hydration heat curve", microstructure_image)
    assert figure_specific_requirement_satisfied("show interface microstructure", microstructure_image)
    assert not figure_specific_requirement_satisfied("show interface microstructure", thermal_curve)


def test_search_figures_detects_visual_intent_and_text_only_negation() -> None:
    assert query_requests_figure("请返回水泥流失量影响因素的曲线图")
    assert query_requests_figure("show passing factor PF curve")
    assert not query_requests_figure("什么是堆石混凝土？请只用文字回答。")
    assert not query_requests_figure("自密实混凝土在 RFC 中起什么作用？不要配图。")


def test_agent_toolbox_search_figures_suppresses_text_only_query(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = make_toolbox(db).search_figures("什么是堆石混凝土？请只用文字回答。")

    assert result.tool_name == "search_figures"
    assert result.call.succeeded
    assert result.refused
    assert result.figure_results == []


def test_agent_toolbox_answer_with_citations_reuses_answer_service(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_agent_tool_documents(db)
        result = make_toolbox(db).answer_with_citations(
            "What affects filling capacity in rock-filled concrete?",
            retrieval_mode="hybrid",
            top_k=2,
        )

    assert result.tool_name == "answer_with_citations"
    assert result.call.succeeded
    assert not result.refused
    assert result.answer is not None
    assert result.citations == [1]
    assert result.sources


def test_agent_toolbox_list_and_get_source_detail_are_read_only_source_tools(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        SourceRepository(db).create_source(source_record())
        toolbox = make_toolbox(db)

        listed = toolbox.list_sources(limit=5)
        detailed = toolbox.get_source_detail("rfc_source_001")

    assert listed.tool_name == "list_sources"
    assert listed.call.succeeded
    assert listed.sources[0].source_id == "rfc_source_001"
    assert listed.sources[0].fulltext_permission == "metadata_only"
    assert detailed.tool_name == "get_source_detail"
    assert detailed.call.succeeded
    assert detailed.sources[0].title == "Filling Capacity Evaluation of Self-Compacting Concrete"


def test_agent_toolbox_get_source_detail_returns_auditable_failure(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = make_toolbox(db).get_source_detail("missing_source")

    assert result.refused
    assert not result.call.succeeded
    assert result.call.error == "Source missing_source was not found."
    assert result.refusal_reason == "Source missing_source was not found."


def test_agent_toolbox_rejects_invalid_tool_parameters(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        toolbox = make_toolbox(db)
        search_result = toolbox.search_knowledge("   ")
        list_result = toolbox.list_sources(limit=0)

    assert search_result.refused
    assert not search_result.call.succeeded
    assert "query" in (search_result.refusal_reason or "")
    assert list_result.refused
    assert "limit" in (list_result.refusal_reason or "")
