from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.db.repositories import ConversationRepository, MessageCreate
from app.db.session import create_sqlite_engine, get_db
from app.main import app


@contextmanager
def make_test_client(tmp_path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "conversations_api.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_conversation_api_creates_and_lists_conversations(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        create_response = client.post("/conversations", json={"title": "阶段 24 测试会话"})
        list_response = client.get("/conversations")

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["title"] == "阶段 24 测试会话"
    assert created["id"] > 0
    assert created["created_at"]
    assert created["updated_at"]

    assert list_response.status_code == 200
    listed = list_response.json()["conversations"]
    assert [item["id"] for item in listed] == [created["id"]]
    assert listed[0]["title"] == "阶段 24 测试会话"


def test_conversation_api_uses_default_title_for_blank_create(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        response = client.post("/conversations", json={"title": "   "})

    assert response.status_code == 200
    assert response.json()["title"] == "新对话"


def test_conversation_api_returns_messages_with_metadata(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        conversation_id = seed_conversation(client)
        response = client.get(f"/conversations/{conversation_id}/messages")

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation"]["id"] == conversation_id
    assert [message["role"] for message in payload["messages"]] == ["user", "assistant"]
    assert payload["messages"][1]["mode"] == "default"
    assert payload["messages"][1]["metadata"] == {
        "citations": [1],
        "refusal_category": None,
    }


def test_conversation_api_deletes_conversation_and_messages(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        conversation_id = seed_conversation(client)
        delete_response = client.delete(f"/conversations/{conversation_id}")
        get_response = client.get(f"/conversations/{conversation_id}/messages")

    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}
    assert get_response.status_code == 404


def test_conversation_api_returns_404_for_missing_conversation(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        get_response = client.get("/conversations/999/messages")
        delete_response = client.delete("/conversations/999")

    assert get_response.status_code == 404
    assert delete_response.status_code == 404


def test_conversation_api_clamps_list_limit(tmp_path) -> None:
    with make_test_client(tmp_path) as client:
        first = client.post("/conversations", json={"title": "A"}).json()
        client.post("/conversations", json={"title": "B"})
        response = client.get("/conversations?limit=1")

    assert response.status_code == 200
    assert len(response.json()["conversations"]) == 1
    assert response.json()["conversations"][0]["id"] != first["id"]


def seed_conversation(client: TestClient) -> int:
    response = client.post("/conversations", json={"title": "消息测试"})
    conversation_id = response.json()["id"]

    override_get_db = app.dependency_overrides[get_db]
    db_generator = override_get_db()
    db = next(db_generator)
    try:
        repository = ConversationRepository(db)
        repository.add_message(
            MessageCreate(
                conversation_id=conversation_id,
                role="user",
                content="什么影响填充性能？",
            )
        )
        repository.add_message(
            MessageCreate(
                conversation_id=conversation_id,
                role="assistant",
                content="填充性能受流动性影响。",
                mode="default",
                metadata={"citations": [1], "refusal_category": None},
            )
        )
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass
    return conversation_id
