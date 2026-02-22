"""Tests for search service SQL sorting behavior."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.queries import ProductQueryParams
from app.services.search import fetch_products


def _sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True})).lower()


@pytest.mark.asyncio
async def test_unit_price_sort_uses_product_unit_price() -> None:
    """Sort by unit_price should use products.unit_price column."""
    captured_statements = []

    async def execute_side_effect(statement):
        captured_statements.append(statement)
        result = MagicMock()
        if len(captured_statements) == 1:
            result.scalar_one.return_value = 0
        else:
            result.all.return_value = []
        return result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_side_effect)

    await fetch_products(
        session,
        ProductQueryParams(sort="unit_price", page=1, page_size=20),
    )

    sql = _sql(captured_statements[1])
    assert "order by" in sql
    assert "unit_price" in sql


@pytest.mark.asyncio
async def test_unique_products_row_selection_uses_requested_sort() -> None:
    """unique_products row_number ordering should follow requested sort."""
    captured_statements = []

    async def execute_side_effect(statement):
        captured_statements.append(statement)
        result = MagicMock()
        if len(captured_statements) == 1:
            result.scalar_one.return_value = 0
        else:
            result.all.return_value = []
        return result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_side_effect)

    await fetch_products(
        session,
        ProductQueryParams(unique_products=True, sort="total_price", page=1, page_size=20),
    )

    sql = _sql(captured_statements[1])
    rownum_start = sql.find("row_number() over")
    rownum_window = sql[rownum_start:rownum_start + 500]
    assert "order by coalesce(case when (prices.promo_price_nzd is not null and (prices.promo_ends_at is null or prices.promo_ends_at > now())) then prices.promo_price_nzd end, prices.price_nzd) asc" in rownum_window
    assert "order by ((prices.price_nzd - coalesce" not in rownum_window


@pytest.mark.asyncio
async def test_default_sort_is_total_price() -> None:
    """Default sort should be total_price (effective price ascending)."""
    captured_statements = []

    async def execute_side_effect(statement):
        captured_statements.append(statement)
        result = MagicMock()
        if len(captured_statements) == 1:
            result.scalar_one.return_value = 0
        else:
            result.all.return_value = []
        return result

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=execute_side_effect)

    await fetch_products(
        session,
        ProductQueryParams(page=1, page_size=20),
    )

    sql = _sql(captured_statements[1])
    assert "order by" in sql
    assert "coalesce" in sql
