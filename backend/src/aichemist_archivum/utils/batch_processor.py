"""
Batch processor for parallel task execution.

This module provides utilities for processing multiple items concurrently.
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


class BatchProcessor:
    """Processes items in batches with concurrency control."""

    def __init__(self, max_workers: int = 5) -> None:
        """
        Initialize the batch processor.

        Args:
            max_workers: Maximum number of concurrent workers
        """
        self.max_workers = max_workers

    async def process_batch(
        self,
        items: Iterable[T],
        processor: Callable[[T], Awaitable[R]],
        batch_size: int = 10,
    ) -> list[R]:
        """
        Process items in batches.

        Args:
            items: Items to process
            processor: Async function to process each item (must return awaitable)
            batch_size: Number of items per batch

        Returns:
            List of processed results
        """
        semaphore = asyncio.Semaphore(self.max_workers)

        async def process_item(item: T) -> R:
            async with semaphore:
                result = processor(item)
                if isinstance(result, Awaitable):
                    return await result
                return result

        tasks = [process_item(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return successful results
        successful_results: list[R] = []
        for result in results:
            if not isinstance(result, BaseException):
                successful_results.append(result)

        return successful_results


__all__ = ["BatchProcessor"]
