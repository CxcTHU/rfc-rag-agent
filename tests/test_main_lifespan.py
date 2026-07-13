from contextlib import nullcontext
from types import SimpleNamespace

import app.main as main
from app.core.config import Settings


def test_bm25_startup_warmup_defaults_to_enabled() -> None:
    assert Settings().bm25_startup_warmup_enabled is True


def test_startup_warmup_builds_bm25_corpus_before_accepting_requests(monkeypatch) -> None:
    session = object()
    seen: list[object] = []
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(bm25_startup_warmup_enabled=True),
    )
    monkeypatch.setattr(main, "SessionLocal", lambda: nullcontext(session))
    monkeypatch.setattr(
        main,
        "warm_bm25_corpus",
        lambda db: seen.append(db) or 3,
    )

    main.warm_retrieval_startup_caches()

    assert seen == [session]


def test_startup_warmup_can_be_disabled_without_opening_a_session(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(bm25_startup_warmup_enabled=False),
    )
    monkeypatch.setattr(
        main,
        "SessionLocal",
        lambda: (_ for _ in ()).throw(AssertionError("session should stay closed")),
    )

    main.warm_retrieval_startup_caches()
