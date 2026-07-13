from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.session import create_sqlite_engine
from app.services.retrieval.embedding import DeterministicEmbeddingProvider
from app.services.retrieval.hybrid_search import HybridSearchService
from app.services.retrieval.route_context import reset_phase64_route_kind
from app.services.retrieval.route_context import set_phase64_route_kind


def _service(tmp_path) -> HybridSearchService:
    engine = create_sqlite_engine(f"sqlite:///{(tmp_path / 'fanout.sqlite').as_posix()}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return HybridSearchService(
        SessionLocal(),
        DeterministicEmbeddingProvider(dimension=32),
        parallel=False,
        reranking_enabled=False,
    )


def test_all_plan_approved_channels_start_before_release(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    started = {name: Event() for name in ("bm25", "vector", "graph")}
    release = Event()

    def blocking_channel(channel: str, query: str, fetch_k: int, *, db, channel_plan):
        del query, fetch_k, db, channel_plan
        started[channel].set()
        assert release.wait(1.0)
        return []

    monkeypatch.setattr(service, "_search_eligible_channel", blocking_channel, raising=False)
    channel_plan = {"eligible_channels": ("bm25", "vector", "graph")}
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            service._search_eligible_channels_parallel,
            "裂缝因果关系",
            8,
            channel_plan,
        )
        assert all(event.wait(1.0) for event in started.values())
        release.set()
        assert future.result(timeout=2.0) == {"bm25": [], "vector": [], "graph": []}


def test_unapproved_table_and_figure_channels_never_start(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    calls: list[str] = []

    def record_channel(channel: str, query: str, fetch_k: int, *, db, channel_plan):
        del query, fetch_k, db, channel_plan
        calls.append(channel)
        return []

    monkeypatch.setattr(service, "_search_eligible_channel", record_channel, raising=False)
    results = service._search_eligible_channels_parallel(
        "堆石混凝土优势",
        8,
        {"eligible_channels": ("bm25", "vector")},
    )

    assert calls == ["bm25", "vector"]
    assert results == {"bm25": [], "vector": []}


def test_fast_route_never_uses_multichannel_fanout_when_flag_is_on(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    original = service.settings.phase64_retrieval_fanout_enabled
    token = set_phase64_route_kind("fast")
    service.settings.phase64_retrieval_fanout_enabled = True
    monkeypatch.setattr(
        service,
        "_search_eligible_channels_parallel",
        lambda *_args, **_kwargs: pytest.fail("fast route must not fan out"),
    )
    try:
        service.search("ordinary text", top_k=5)
    finally:
        service.settings.phase64_retrieval_fanout_enabled = original
        reset_phase64_route_kind(token)


def test_complex_fanout_never_exceeds_global_inflight_limit(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path)
    original = service.settings.phase64_retrieval_max_inflight
    service.settings.phase64_retrieval_max_inflight = 2
    active_workers = 0
    maximum_active_workers = 0
    active_lock = Lock()
    third_worker_started = Event()
    release = Event()

    def blocking_channel(channel: str, query: str, fetch_k: int, *, db, channel_plan):
        nonlocal active_workers, maximum_active_workers
        del channel, query, fetch_k, db, channel_plan
        with active_lock:
            active_workers += 1
            maximum_active_workers = max(maximum_active_workers, active_workers)
            if active_workers >= 3:
                third_worker_started.set()
        try:
            assert release.wait(1.0)
            return []
        finally:
            with active_lock:
                active_workers -= 1

    monkeypatch.setattr(service, "_search_eligible_channel", blocking_channel, raising=False)
    channel_plan = {"eligible_channels": ("bm25", "vector", "graph")}
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    service._search_eligible_channels_parallel,
                    "裂缝因果关系",
                    8,
                    channel_plan,
                )
                for _ in range(2)
            ]
            assert not third_worker_started.wait(0.2)
            release.set()
            for future in futures:
                future.result(timeout=2.0)
        assert maximum_active_workers <= 2
    finally:
        service.settings.phase64_retrieval_max_inflight = original
