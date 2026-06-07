from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    DocumentCreate,
    DocumentRepository,
    QuestionAnswerLogRepository,
)
from app.db.session import create_sqlite_engine
from app.services.brain.config import DEFAULT_WORKFLOW_STEPS, RetrievalConfig
from app.services.brain.service import BrainService, rewrite_contextual_question
from app.services.brain.workflow import DEFAULT_REFUSAL_ANSWER
from app.services.generation.chat_model import DeterministicChatModelProvider
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.vector_index import VectorIndexService


def make_session(tmp_path):
    database_path = tmp_path / "brain_service.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def seed_brain_documents(db) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Thermal and filling guide",
            source_type="local_file",
            source_path="brain-guide.md",
            file_name="brain-guide.md",
            file_extension=".md",
            content_hash="brain-service-guide-hash",
            raw_path="data/raw/brain-guide.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Thermal control reduces hydration heat in rock-filled concrete dams.",
                char_count=68,
                heading_path="Thermal",
                start_char=0,
                end_char=68,
            ),
            ChunkCreate(
                chunk_index=1,
                content="Filling capacity depends on self-compacting concrete flowability.",
                char_count=65,
                heading_path="Filling",
                start_char=69,
                end_char=134,
            ),
        ],
    )


def seed_context_documents(db) -> None:
    DocumentRepository(db).create_with_chunks(
        DocumentCreate(
            title="Creep behaviour of rock-filled concrete",
            source_type="local_file",
            source_path="creep.md",
            file_name="creep.md",
            file_extension=".md",
            content_hash="brain-service-creep-hash",
            raw_path="data/raw/creep.md",
        ),
        [
            ChunkCreate(
                chunk_index=0,
                content="Creep behaviour describes long-term deformation of rock-filled concrete.",
                char_count=74,
                heading_path="Creep",
                start_char=0,
                end_char=74,
            ),
        ],
    )


def make_brain_service(db, embedding_provider=None, log_answers=True) -> BrainService:
    return BrainService(
        db=db,
        chat_model_provider=DeterministicChatModelProvider(),
        embedding_provider=embedding_provider
        or DeterministicEmbeddingProvider(dimension=32),
        log_answers=log_answers,
    )


class ConstantEmbeddingProvider:
    provider_name = "constant"
    model_name = "constant-v1"
    dimension = 2

    def embed_texts(self, texts):
        return [[1.0, 0.0] for _text in texts]

    def embed_query(self, query):
        return [1.0, 0.0]


def test_brain_service_runs_default_workflow_with_keyword_retrieval(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_brain_documents(db)
        result = make_brain_service(db).answer(
            "thermal control",
            config=RetrievalConfig(retrieval_mode="keyword", top_k=2),
        )

    assert not result.refused
    assert result.retrieval_mode == "keyword"
    assert result.citations == [1]
    assert result.sources[0].document_title == "Thermal and filling guide"
    assert [step.name for step in result.workflow_steps] == list(DEFAULT_WORKFLOW_STEPS)
    assert all(step.succeeded for step in result.workflow_steps)


def test_brain_service_auto_falls_back_to_keyword_when_vector_index_is_missing(
    tmp_path,
) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_brain_documents(db)
        result = make_brain_service(db).answer(
            "thermal control",
            config=RetrievalConfig(retrieval_mode="auto", top_k=2),
        )

    assert not result.refused
    assert result.retrieval_mode == "keyword"
    assert result.workflow_steps[2].name == "retrieve"
    assert "mode=keyword" in result.workflow_steps[2].output_summary


def test_brain_service_optional_rerank_truncates_context(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_brain_documents(db)
        result = make_brain_service(db).answer(
            "thermal filling capacity",
            config=RetrievalConfig(
                retrieval_mode="keyword",
                top_k=2,
                rerank_top_n=1,
            ),
        )

    assert not result.refused
    assert len(result.sources) == 1
    rerank_step = result.workflow_steps[3]
    assert rerank_step.name == "optional_rerank"
    assert rerank_step.output_summary == "kept=1"


def test_rewrite_contextual_question_uses_recent_history_for_pronoun() -> None:
    rewritten = rewrite_contextual_question(
        "它有哪些研究？",
        ["堆石混凝土徐变有什么研究？"],
    )

    assert rewritten == "堆石混凝土徐变有什么研究？；追问：它有哪些研究？"


def test_rewrite_contextual_question_leaves_specific_question_unchanged() -> None:
    question = "堆石混凝土徐变有什么研究？"

    assert rewrite_contextual_question(question, ["上一轮问题"]) == question


def test_brain_service_rewrites_contextual_question_before_retrieval(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_context_documents(db)
        result = make_brain_service(db).answer(
            "它有哪些研究？",
            config=RetrievalConfig(
                retrieval_mode="keyword",
                top_k=2,
                max_history=1,
            ),
            history=["堆石混凝土徐变有什么研究？"],
        )

    assert not result.refused
    assert result.question == "它有哪些研究？"
    assert result.sources[0].document_title == "Creep behaviour of rock-filled concrete"
    assert result.workflow_steps[0].output_summary == "kept_history=1"
    assert result.workflow_steps[1].output_summary == "query rewritten from recent history"


def test_brain_service_does_not_rewrite_when_history_is_disabled(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        seed_context_documents(db)
        result = make_brain_service(db).answer(
            "它有哪些研究？",
            config=RetrievalConfig(
                retrieval_mode="keyword",
                top_k=2,
                max_history=0,
            ),
            history=["堆石混凝土徐变有什么研究？"],
        )

    assert result.refused
    assert result.workflow_steps[0].output_summary == "kept_history=0"
    assert result.workflow_steps[1].output_summary == "query unchanged"


def test_brain_service_refuses_and_logs_when_no_results(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        result = make_brain_service(db).answer(
            "missing context",
            config=RetrievalConfig(retrieval_mode="keyword"),
        )
        logs = QuestionAnswerLogRepository(db).list_logs()

    assert result.refused
    assert result.answer == DEFAULT_REFUSAL_ANSWER
    assert result.retrieval_mode == "keyword"
    assert result.workflow_steps[-1].name == "generate_answer"
    assert result.workflow_steps[-1].output_summary == "refused=True"
    assert len(logs) == 1
    assert logs[0].refused is True


def test_brain_service_supports_vector_retrieval(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        embedding_provider = DeterministicEmbeddingProvider(dimension=32)
        seed_brain_documents(db)
        VectorIndexService(db, embedding_provider).build_index()

        result = make_brain_service(db, embedding_provider=embedding_provider).answer(
            "thermal control",
            config=RetrievalConfig(retrieval_mode="vector", top_k=2),
        )

    assert not result.refused
    assert result.retrieval_mode == "vector"
    assert result.model_provider == "deterministic"
    assert result.model_name == "rule-based-chat-v1"


def test_brain_service_refuses_low_evidence_vector_results(tmp_path) -> None:
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        embedding_provider = ConstantEmbeddingProvider()
        seed_brain_documents(db)
        VectorIndexService(db, embedding_provider).build_index()

        result = make_brain_service(db, embedding_provider=embedding_provider).answer(
            "zqxjvblorptasticprotocol",
            config=RetrievalConfig(retrieval_mode="vector", top_k=2),
        )

    assert result.refused
    assert result.sources == []
    assert result.citations == []
    assert "evidence" in (result.refusal_reason or "")
    assert result.workflow_steps[-1].output_summary == "refused=True low_evidence"
