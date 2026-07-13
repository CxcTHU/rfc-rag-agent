from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock


_LIMITERS: dict[int, BoundedSemaphore] = {}
_LIMITERS_LOCK = Lock()


def _limiter_for(max_inflight: int) -> BoundedSemaphore:
    limit = max(1, int(max_inflight))
    with _LIMITERS_LOCK:
        limiter = _LIMITERS.get(limit)
        if limiter is None:
            limiter = BoundedSemaphore(limit)
            _LIMITERS[limit] = limiter
        return limiter


@contextmanager
def phase64_fanout_slot(max_inflight: int) -> Iterator[None]:
    limiter = _limiter_for(max_inflight)
    limiter.acquire()
    try:
        yield
    finally:
        limiter.release()
