"""Asynchronous SQLite operations for The Aichemist Codex."""

import logging
from pathlib import Path
from typing import Any, Literal, TypeVar, overload

import aiosqlite

logger: logging.Logger = logging.getLogger(__name__)

# Type for different return formats
RowFormat = Literal["row", "tuple", "dict"]
T = TypeVar("T", aiosqlite.Row, tuple[Any, ...], dict[str, Any])


class AsyncSQL:
    """Provides asynchronous SQL operations."""

    def __init__(self, db_path: Path) -> None:
        """Initialize with database path."""
        self.db_path = db_path

    async def execute(
        self, query: str, params: tuple[Any, ...] = (), commit: bool = False
    ) -> None:
        """Execute a SQL query asynchronously."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                await db.execute(query, params)
                if commit:
                    await db.commit()
        except Exception as e:
            logger.error(f"Error executing query: {query} with params {params}: {e}")

    @overload
    async def fetchall(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        return_format: Literal["row"] = "row",
    ) -> list[aiosqlite.Row]: ...

    @overload
    async def fetchall(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        return_format: Literal["tuple"] = "tuple",
    ) -> list[tuple[Any, ...]]: ...

    @overload
    async def fetchall(
        self,
        query: str,
        params: tuple[Any, ...] = (),
        return_format: Literal["dict"] = "dict",
    ) -> list[dict[str, Any]]: ...

    async def fetchall(
        self, query: str, params: tuple[Any, ...] = (), return_format: RowFormat = "row"
    ) -> list[aiosqlite.Row] | list[tuple[Any, ...]] | list[dict[str, Any]]:
        """
        Fetch all rows from a query asynchronously.

        Args:
            query: SQL query to execute
            params: Query parameters
            return_format: Format for returned rows ('row', 'tuple', or 'dict')
                - 'row': Return aiosqlite.Row objects (default)
                - 'tuple': Return tuples
                - 'dict': Return dictionaries

        Returns:
            List of query results in the specified format
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()

                    if return_format == "row":
                        return rows
                    elif return_format == "tuple":
                        return [tuple(row) for row in rows]
                    else:  # dict
                        return [dict(row) for row in rows]
        except Exception as e:
            logger.error(
                f"Error fetching rows for query: {query} with params {params}: {e}"
            )
            return []

    async def fetchone(
        self, query: str, params: tuple[Any, ...] = (), return_format: RowFormat = "row"
    ) -> aiosqlite.Row | tuple[Any, ...] | dict[str, Any] | None:
        """
        Fetch one row from a query asynchronously.

        Args:
            query: SQL query to execute
            params: Query parameters
            return_format: Format for returned row ('row', 'tuple', or 'dict')
                - 'row': Return aiosqlite.Row object (default)
                - 'tuple': Return tuple
                - 'dict': Return dictionary

        Returns:
            Query result in the specified format or None if no result
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, params) as cursor:
                    row = await cursor.fetchone()
                    if row is None:
                        return None

                    if return_format == "row":
                        return row
                    elif return_format == "tuple":
                        return tuple(row)
                    else:  # dict
                        return dict(row)
        except Exception as e:
            logger.error(
                f"Error fetching row for query: {query} with params {params}: {e}"
            )
            return None

    async def executemany(self, query: str, params_list: list[tuple]) -> None:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executemany(query, params_list)
                await db.commit()
        except Exception as e:
            logger.error(
                f"Error executing many for query: {query} with params "
                f"{params_list}: {e}"
            )
