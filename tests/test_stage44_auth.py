from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token, password_hash, verify_password
from app.db.models import Base, User
from app.db.session import create_sqlite_engine, get_db
from app.main import app


@contextmanager
def make_auth_client(tmp_path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "stage44_auth.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_settings() -> Settings:
        return Settings(
            auth_enabled=True,
            jwt_secret_key="stage44-test-secret",
            database_url=f"sqlite:///{database_path.as_posix()}",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_settings
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_stage44_password_hash_uses_bcrypt_and_verifies() -> None:
    hashed = password_hash("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$2")
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_stage44_register_login_and_me_do_not_expose_password_hash(tmp_path) -> None:
    with make_auth_client(tmp_path) as client:
        register_response = client.post(
            "/auth/register",
            json={
                "username": "alice",
                "email": "alice@example.com",
                "password": "stage44-password",
            },
        )
        login_response = client.post(
            "/auth/login",
            json={
                "username_or_email": "alice",
                "password": "stage44-password",
            },
        )

        token = login_response.json()["access_token"]
        me_response = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert register_response.status_code == 200
    assert "password_hash" not in register_response.text
    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"
    assert login_response.json()["expires_in"] > 0
    payload = decode_access_token(
        token,
        settings=Settings(auth_enabled=True, jwt_secret_key="stage44-test-secret"),
    )
    assert payload["sub"] == str(register_response.json()["id"])
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "alice"
    assert "password" not in me_response.text


def test_stage44_auth_protects_agent_and_conversation_routes(tmp_path) -> None:
    with make_auth_client(tmp_path) as client:
        public_health = client.get("/health")
        public_health_details = client.get("/health/details")
        public_register = client.post(
            "/auth/register",
            json={
                "username": "bob",
                "email": "bob@example.com",
                "password": "stage44-password",
            },
        )
        public_login = client.post(
            "/auth/login",
            json={
                "username_or_email": "bob",
                "password": "stage44-password",
            },
        )
        unauth_agent = client.post("/agent/query", json={"question": "hello"})
        unauth_stream = client.post("/agent/query/stream", json={"question": "hello"})
        unauth_conversations = client.get("/conversations")

    assert public_health.status_code == 200
    assert public_health_details.status_code == 200
    assert public_register.status_code == 200
    assert public_login.status_code == 200
    assert unauth_agent.status_code == 401
    assert unauth_stream.status_code == 401
    assert unauth_conversations.status_code == 401


def test_stage44_conversations_are_isolated_by_user(tmp_path) -> None:
    with make_auth_client(tmp_path) as client:
        alice_token = register_and_login(client, "alice", "alice@example.com")
        bob_token = register_and_login(client, "bob", "bob@example.com")
        alice_headers = {"Authorization": f"Bearer {alice_token}"}
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        alice_conversation = client.post(
            "/conversations",
            json={"title": "Alice private"},
            headers=alice_headers,
        ).json()
        bob_conversation = client.post(
            "/conversations",
            json={"title": "Bob private"},
            headers=bob_headers,
        ).json()

        alice_list = client.get("/conversations", headers=alice_headers)
        bob_list = client.get("/conversations", headers=bob_headers)
        bob_reads_alice = client.get(
            f"/conversations/{alice_conversation['id']}/messages",
            headers=bob_headers,
        )
        alice_deletes_bob = client.delete(
            f"/conversations/{bob_conversation['id']}",
            headers=alice_headers,
        )

    assert [item["title"] for item in alice_list.json()["conversations"]] == [
        "Alice private"
    ]
    assert [item["title"] for item in bob_list.json()["conversations"]] == ["Bob private"]
    assert bob_reads_alice.status_code == 404
    assert alice_deletes_bob.status_code == 404


def test_stage44_agent_query_rejects_other_users_conversation(tmp_path) -> None:
    with make_auth_client(tmp_path) as client:
        alice_token = register_and_login(client, "alice", "alice@example.com")
        bob_token = register_and_login(client, "bob", "bob@example.com")
        alice_headers = {"Authorization": f"Bearer {alice_token}"}
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        alice_conversation = client.post(
            "/conversations",
            json={"title": "Alice private"},
            headers=alice_headers,
        ).json()
        bob_query_alice = client.post(
            "/agent/query",
            json={
                "question": "你用的什么模型？",
                "conversation_id": alice_conversation["id"],
            },
            headers=bob_headers,
        )

    assert bob_query_alice.status_code == 404


def test_stage44_user_password_hash_is_stored_not_plaintext(tmp_path) -> None:
    with make_auth_client(tmp_path) as client:
        client.post(
            "/auth/register",
            json={
                "username": "carol",
                "email": "carol@example.com",
                "password": "stage44-password",
            },
        )

        override_get_db = app.dependency_overrides[get_db]
        db_generator = override_get_db()
        db = next(db_generator)
        try:
            user = db.query(User).filter_by(username="carol").one()
            stored_hash = user.password_hash
        finally:
            try:
                next(db_generator)
            except StopIteration:
                pass

    assert stored_hash != "stage44-password"
    assert stored_hash.startswith("$2")


def register_and_login(client: TestClient, username: str, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": "stage44-password",
        },
    )
    assert response.status_code == 200
    login_response = client.post(
        "/auth/login",
        json={
            "username_or_email": username,
            "password": "stage44-password",
        },
    )
    assert login_response.status_code == 200
    return str(login_response.json()["access_token"])
