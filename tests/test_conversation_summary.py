from collections.abc import Sequence

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ConversationRepository, MessageCreate, deserialize_metadata
from app.db.session import create_sqlite_engine
from app.services.conversation.history import (
    history_from_messages,
    summarize_conversation_if_needed,
)
from app.services.generation.chat_model import ChatMessage, ChatModelResult


class SummaryTestProvider:
    provider_name = "summary-test"
    model_name = "summary-test-v1"

    def generate(self, messages: Sequence[ChatMessage]) -> ChatModelResult:
        latest_user = next(message.content for message in reversed(messages) if message.role == "user")
        return ChatModelResult(
            answer=f"摘要：{latest_user[:80]}",
            provider=self.provider_name,
            model_name=self.model_name,
            raw_response=None,
        )


def make_repository(tmp_path) -> ConversationRepository:
    database_path = tmp_path / "conversation_summary.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    return ConversationRepository(db)


def test_summarize_conversation_creates_summary_after_threshold(tmp_path) -> None:
    repository = make_repository(tmp_path)
    conversation = repository.create_conversation()
    for index in range(18):
        repository.add_message(
            MessageCreate(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"消息 {index}",
            )
        )

    summary = summarize_conversation_if_needed(
        repository=repository,
        conversation_id=conversation.id,
        chat_model_provider=SummaryTestProvider(),
    )
    messages = repository.list_messages(conversation.id)

    assert summary is not None
    assert summary.role == "summary"
    assert summary.content.startswith("摘要：")
    assert messages[-1].role == "summary"
    metadata = deserialize_metadata(summary.metadata_json)
    assert len(metadata["summary_of_message_ids"]) == 12
    assert metadata["kept_recent_non_summary_messages"] == 6


def test_summarize_conversation_skips_until_new_messages_exceed_threshold(tmp_path) -> None:
    repository = make_repository(tmp_path)
    conversation = repository.create_conversation()
    for index in range(18):
        repository.add_message(
            MessageCreate(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"第一批消息 {index}",
            )
        )

    first_summary = summarize_conversation_if_needed(
        repository=repository,
        conversation_id=conversation.id,
        chat_model_provider=SummaryTestProvider(),
    )
    second_summary = summarize_conversation_if_needed(
        repository=repository,
        conversation_id=conversation.id,
        chat_model_provider=SummaryTestProvider(),
    )

    assert first_summary is not None
    assert second_summary is None


def test_history_from_messages_uses_latest_summary_and_recent_messages(tmp_path) -> None:
    repository = make_repository(tmp_path)
    conversation = repository.create_conversation()
    repository.add_message(MessageCreate(conversation_id=conversation.id, role="user", content="旧问题"))
    repository.add_message(MessageCreate(conversation_id=conversation.id, role="summary", content="旧摘要"))
    repository.add_message(MessageCreate(conversation_id=conversation.id, role="user", content="新问题"))
    repository.add_message(
        MessageCreate(
            conversation_id=conversation.id,
            role="assistant",
            content="新回答",
            mode="default",
        )
    )

    history = history_from_messages(repository.list_messages(conversation.id))

    assert history == ["对话摘要：旧摘要", "用户：新问题", "助手：新回答"]
