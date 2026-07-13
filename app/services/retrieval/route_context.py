from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Literal


Phase64RouteKind = Literal["fast", "complex", "legacy"]

_CURRENT_PHASE64_ROUTE_KIND: ContextVar[Phase64RouteKind] = ContextVar(
    "current_phase64_route_kind",
    default="legacy",
)


def set_phase64_route_kind(kind: Phase64RouteKind) -> Token[Phase64RouteKind]:
    return _CURRENT_PHASE64_ROUTE_KIND.set(kind)


def reset_phase64_route_kind(token: Token[Phase64RouteKind]) -> None:
    _CURRENT_PHASE64_ROUTE_KIND.reset(token)


def current_phase64_route_kind() -> Phase64RouteKind:
    return _CURRENT_PHASE64_ROUTE_KIND.get()
