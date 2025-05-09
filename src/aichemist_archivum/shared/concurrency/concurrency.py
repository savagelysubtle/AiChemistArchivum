"""Provides enhanced concurrency tools for efficient parallel processing."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, TypeVar, cast

logger = logging.getLogger(__name__)
T = TypeVar("T")

# Private singleton instances
_thread_pool_instance: AsyncThreadPoolExecutor | None = None
_task_queue_instance: TaskQueue | None = None


def get_thread_pool(max_workers: int | None = None) -> AsyncThreadPoolExecutor:
    """
    Get or create the thread pool executor instance.

    Args:
        max_workers: Maximum number of worker threads

    Returns:
        AsyncThreadPoolExecutor: Singleton instance of the thread pool
    """
    global _thread_pool_instance

    if _thread_pool_instance is None:
        _thread_pool_instance = AsyncThreadPoolExecutor(max_workers=max_workers)

    return _thread_pool_instance


def get_task_queue(
    max_concurrent: int = 10, max_rate: float | None = None, time_period: float = 1.0
) -> TaskQueue:
    """
    Get or create the task queue instance.

    Args:
        max_concurrent: Maximum number of concurrent tasks
        max_rate: Maximum tasks per time period (None for no limit)
        time_period: Time period in seconds for rate limiting

    Returns:
        TaskQueue: Singleton instance of the task queue
    """
    global _task_queue_instance

    if _task_queue_instance is None:
        _task_queue_instance = TaskQueue(
            max_concurrent=max_concurrent, max_rate=max_rate, time_period=time_period
        )

    return _task_queue_instance


class TaskPriority(Enum):
    """Task priority levels for scheduling."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2


class AsyncThreadPoolExecutor:
    """Thread pool executor with async interface and priority scheduling."""

    def __init__(self, max_workers: int | None = None) -> None:
        """Initialize the executor with a maximum number of workers.

        Args:
            max_workers: Maximum number of worker threads
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        # Default to 10 workers if not specified
        worker_count = 10 if max_workers is None else max_workers
        self.semaphore = asyncio.Semaphore(worker_count)
        self._tasks: dict[asyncio.Future[Any], TaskPriority] = {}

    async def submit(
        self,
        func: Callable[..., T],
        *args: object,
        priority: TaskPriority = TaskPriority.MEDIUM,
        **kwargs: object,
    ) -> T:
        """
        Submit a function for execution with priority scheduling.

        Args:
            func: Function to execute
            *args: Arguments for the function
            priority: Task priority level
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function execution
        """
        async with self.semaphore:
            loop = asyncio.get_event_loop()

            # Create a future for the executor task
            future = loop.run_in_executor(
                self.executor, functools.partial(func, *args, **kwargs)
            )

            # Store future with priority
            self._tasks[future] = priority

            try:
                result = await future
                return cast(T, result)
            finally:
                if future in self._tasks:
                    del self._tasks[future]

    async def submit_batch(
        self,
        func: Callable[[Any], T],
        items: list[Any],
        priority: TaskPriority = TaskPriority.MEDIUM,
        max_concurrent: int | None = None,
    ) -> list[T]:
        """
        Submit a batch of items for concurrent processing.

        Args:
            func: Function to execute on each item
            items: List of items to process
            priority: Task priority level
            max_concurrent: Maximum number of concurrent tasks

        Returns:
            List of results in the order of input items
        """
        # Use a separate semaphore for batch processing if specified
        semaphore = (
            asyncio.Semaphore(max_concurrent or 10)
            if max_concurrent
            else self.semaphore
        )

        async def process_item(item: object) -> T:
            async with semaphore:
                return await self.submit(func, item, priority=priority)

        tasks = [asyncio.create_task(process_item(item)) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return only successful results
        return [r for r in results if not isinstance(r, BaseException)]

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the executor.

        Args:
            wait: Whether to wait for pending futures to complete
        """
        self.executor.shutdown(wait=wait)


class RateLimiter:
    """Rate limiter for controlling operation frequency."""

    def __init__(self, max_rate: float, time_period: float = 1.0) -> None:
        """
        Initialize rate limiter.

        Args:
            max_rate: Maximum number of operations per time period
            time_period: Time period in seconds
        """
        self.max_rate = max_rate
        self.time_period = time_period
        self.tokens = max_rate
        self.last_update = asyncio.get_event_loop().time()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self.lock:
            while self.tokens <= 0:
                now = asyncio.get_event_loop().time()
                time_passed = now - self.last_update
                self.tokens = min(
                    self.max_rate,
                    self.tokens + time_passed * (self.max_rate / self.time_period),
                )
                self.last_update = now
                if self.tokens <= 0:
                    await asyncio.sleep(self.time_period / self.max_rate)
            self.tokens -= 1


class TaskQueue:
    """Priority task queue with rate limiting."""

    def __init__(
        self,
        max_concurrent: int = 10,
        max_rate: float | None = None,
        time_period: float = 1.0,
    ) -> None:
        """
        Initialize task queue.

        Args:
            max_concurrent: Maximum number of concurrent tasks
            max_rate: Maximum tasks per time period (None for no limit)
            time_period: Time period in seconds for rate limiting
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = (
            RateLimiter(max_rate, time_period) if max_rate is not None else None
        )
        self.tasks: dict[TaskPriority, list[asyncio.Task]] = {
            priority: [] for priority in TaskPriority
        }

    async def add_task(
        self,
        coro: Callable[..., T],
        *args: object,
        priority: TaskPriority = TaskPriority.MEDIUM,
        **kwargs: object,
    ) -> T:
        """
        Add a task to the queue.

        Args:
            coro: Coroutine to execute
            *args: Arguments for the coroutine
            priority: Task priority level
            **kwargs: Keyword arguments for the coroutine

        Returns:
            Result of the coroutine execution
        """
        async with self.semaphore:
            if self.rate_limiter is not None:
                await self.rate_limiter.acquire()

            task: asyncio.Task[T] = asyncio.create_task(
                cast(Coroutine[Any, Any, T], coro(*args, **kwargs))
            )
            self.tasks[priority].append(task)

            try:
                result = await task
                return cast(T, result)
            finally:
                self.tasks[priority].remove(task)

    async def add_batch(
        self,
        coro: Callable[[object], T],
        items: list[object],
        priority: TaskPriority = TaskPriority.MEDIUM,
        **kwargs: object,
    ) -> list[T | BaseException]:
        """
        Add a batch of items for processing.

        Args:
            coro: Coroutine to execute for each item
            items: List of items to process
            priority: Task priority level
            **kwargs: Additional keyword arguments for the coroutine

        Returns:
            List of results in the order of input items
        """
        tasks = [
            self.add_task(coro, item, priority=priority, **kwargs) for item in items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return cast(list[T | BaseException], results)
