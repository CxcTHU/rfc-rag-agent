"""真实 embedding 服务瞬断/限流时，建索引应有限次退避重试。"""

import pytest

from app.services.retrieval.vector_index import VectorIndexService


class _FlakyProvider:
    """前 N 次 embed_texts 抛异常，之后返回固定维度向量。"""

    provider_name = "fake"
    model_name = "fake-model"
    dimension = 3

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError("Remote end closed connection without response")
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_embed_with_retry_recovers_after_transient_errors(monkeypatch) -> None:
    monkeypatch.setattr("app.services.retrieval.vector_index.time.sleep", lambda *_: None)
    provider = _FlakyProvider(fail_times=2)
    service = VectorIndexService(db=None, embedding_provider=provider)

    result = service._embed_with_retry(["a", "b"], max_retries=3)

    assert result == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert provider.calls == 3  # 2 次失败 + 1 次成功


def test_embed_with_retry_reraises_when_retries_exhausted(monkeypatch) -> None:
    monkeypatch.setattr("app.services.retrieval.vector_index.time.sleep", lambda *_: None)
    provider = _FlakyProvider(fail_times=5)
    service = VectorIndexService(db=None, embedding_provider=provider)

    with pytest.raises(ConnectionError):
        service._embed_with_retry(["a"], max_retries=2)
    assert provider.calls == 3  # 初次 + 2 次重试


def test_embed_with_retry_no_retry_by_default(monkeypatch) -> None:
    monkeypatch.setattr("app.services.retrieval.vector_index.time.sleep", lambda *_: None)
    provider = _FlakyProvider(fail_times=1)
    service = VectorIndexService(db=None, embedding_provider=provider)

    with pytest.raises(ConnectionError):
        service._embed_with_retry(["a"])  # max_retries=0 默认，不重试
    assert provider.calls == 1
