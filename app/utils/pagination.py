"""Reusable pagination helper for SQLAlchemy queries.

Provides a thin wrapper over Flask-SQLAlchemy's ``query.paginate(...)`` that:

- Coerces ``page`` / ``size`` query-string args into safe integers.
- Clamps ``size`` to ``MAX_PAGE_SIZE`` (200) to prevent runaway queries.
- Returns a :class:`PageResult` dataclass exposing the attributes the
  ``render_pagination`` Jinja macro expects (``items``, ``page``, ``per_page``,
  ``total``, ``pages``, ``has_prev``, ``has_next``, ``prev_num``, ``next_num``,
  ``start_index``, ``end_index``).

The companion macro lives at ``app/templates/partials/pagination.html``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from flask import request

logger = logging.getLogger(__name__)

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50
ALLOWED_SIZES = (25, 50, 100)


@dataclass
class PageResult:
    """Lightweight pagination result wrapper used by the render_pagination macro."""

    items: Iterable[Any]
    page: int
    per_page: int
    total: int
    pages: int
    has_prev: bool
    has_next: bool
    prev_num: Optional[int]
    next_num: Optional[int]
    start_index: int
    end_index: int


def paginate(
    query: Any,
    page: Optional[int] = None,
    size: Optional[int] = None,
) -> PageResult:
    """Paginate a SQLAlchemy query, returning a :class:`PageResult`.

    Args:
        query: A SQLAlchemy query (must support Flask-SQLAlchemy's
            ``.paginate(page, per_page, error_out)`` interface).
        page: 1-based page number. Falls back to ``request.args["page"]``,
            then ``1``. Negative / zero values are clamped to ``1``.
        size: Per-page row count. Falls back to ``request.args["size"]``,
            then :data:`DEFAULT_PAGE_SIZE`. Clamped to
            ``[1, MAX_PAGE_SIZE]``.

    Returns:
        :class:`PageResult` with derived ``start_index`` / ``end_index``
        attributes for "Showing X to Y of Z" status text.
    """
    if page is None:
        page = request.args.get("page", 1, type=int)
    if size is None:
        size = request.args.get("size", DEFAULT_PAGE_SIZE, type=int)

    # Defensive coercion — request.args.get(type=int) can return None for malformed input
    page = max(1, int(page or 1))
    size = max(1, min(int(size or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))

    pag = query.paginate(page=page, per_page=size, error_out=False)

    start_index = ((pag.page - 1) * pag.per_page) + 1 if pag.total else 0
    end_index = min(pag.page * pag.per_page, pag.total)

    return PageResult(
        items=pag.items,
        page=pag.page,
        per_page=pag.per_page,
        total=pag.total,
        pages=pag.pages,
        has_prev=pag.has_prev,
        has_next=pag.has_next,
        prev_num=pag.prev_num,
        next_num=pag.next_num,
        start_index=start_index,
        end_index=end_index,
    )
