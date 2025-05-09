"""Asynchronous file operations for The Aichemist Codex."""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator, AsyncIterable, Callable
from pathlib import Path
from typing import Any, cast

import aiofiles  # type: ignore
import aiofiles.os  # type: ignore

from the_aichemist_codex.infrastructure.utils.common.safety import SafeFileHandler

logger = logging.getLogger(__name__)


class AsyncFileIO:
    """Provides comprehensive asynchronous file I/O utilities."""

    @staticmethod
    async def read_text(file_path: Path) -> str:
        """Reads file content asynchronously.

        Args:
            file_path: Path to the file to read

        Returns:
            The file content as a string, or an error message if the file can't be read
        """
        if SafeFileHandler.should_ignore(file_path):
            logger.info(f"Skipping ignored file: {file_path}")
            return f"# Skipped ignored file: {file_path}"

        try:
            async with aiofiles.open(file_path, encoding="utf-8") as f:
                content = await f.read()
                return cast(str, content)
        except UnicodeDecodeError as e:
            logger.error(f"Encoding error in {file_path}: {e}")
            return f"# Encoding error: {e}"
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return f"# Error reading file: {e}"

    @staticmethod
    async def read_binary(file_path: Path) -> bytes:
        """Reads binary file content asynchronously.

        Skips files that match the default ignore patterns using `SafeFileHandler`.

        Args:
            file_path: Path to the binary file to read

        Returns:
            The file content as bytes, or empty bytes if the file can't be read
        """
        if SafeFileHandler.should_ignore(file_path):
            logger.info(f"Skipping ignored binary file: {file_path}")
            return b""

        try:
            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()
                return cast(bytes, content)
        except Exception as e:
            logger.error(f"Error reading binary file {file_path}: {e}")
            return b""

    @staticmethod
    async def write(file_path: Path, content: str, encoding: str = "utf-8") -> bool:
        """Writes string content to a file asynchronously.

        Args:
            file_path: Path where the file should be written
            content: String content to write
            encoding: File encoding to use

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(file_path.parent, exist_ok=True)

            async with aiofiles.open(file_path, "w", encoding=encoding) as f:
                await f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error writing to {file_path}: {e}")
            return False

    @staticmethod
    async def write_binary(file_path: Path, content: bytes) -> bool:
        """Writes binary content to a file asynchronously.

        Args:
            file_path: Path where the file should be written
            content: Binary content to write

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(file_path.parent, exist_ok=True)

            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error writing binary data to {file_path}: {e}")
            return False

    @staticmethod
    async def append(file_path: Path, content: str, encoding: str = "utf-8") -> bool:
        """Appends string content to a file asynchronously.

        Args:
            file_path: Path where the content should be appended
            content: String content to append
            encoding: File encoding to use

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(file_path.parent, exist_ok=True)

            async with aiofiles.open(file_path, "a", encoding=encoding) as f:
                await f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error appending to {file_path}: {e}")
            return False

    @staticmethod
    async def read_lines(file_path: Path) -> list[str]:
        """Reads file lines asynchronously.

        Args:
            file_path: Path to the file to read

        Returns:
            List of lines from the file, or empty list on error
        """
        if SafeFileHandler.should_ignore(file_path):
            logger.info(f"Skipping ignored file: {file_path}")
            return []

        try:
            async with aiofiles.open(file_path, encoding="utf-8") as f:
                lines = await f.readlines()
                return cast(list[str], lines)
        except Exception as e:
            logger.error(f"Error reading lines from {file_path}: {e}")
            return []

    @staticmethod
    async def read_json(file_path: Path) -> dict[Any, Any]:
        """Reads and parses JSON file asynchronously.

        Args:
            file_path: Path to the JSON file

        Returns:
            Parsed JSON object or empty dict on error
        """
        import json

        try:
            content = await AsyncFileIO.read_text(file_path)
            if content.startswith("#"):  # Error reading file
                return {}
            parsed_json = json.loads(content)
            return cast(dict[Any, Any], parsed_json)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error parsing JSON from {file_path}: {e}")
            return {}

    @staticmethod
    async def write_json(file_path: Path, data: object, indent: int = 4) -> bool:
        """Writes data as JSON to a file asynchronously.

        Args:
            file_path: Path where the JSON should be written
            data: Data to serialize as JSON
            indent: Number of spaces for indentation

        Returns:
            True if successful, False otherwise
        """
        import json

        try:
            json_str = json.dumps(data, indent=indent)
            return await AsyncFileIO.write(file_path, json_str)
        except Exception as e:
            logger.error(f"Error writing JSON to {file_path}: {e}")
            return False

    @staticmethod
    async def exists(file_path: Path) -> bool:
        """Checks if a file exists asynchronously.

        Args:
            file_path: Path to check

        Returns:
            True if the file exists, False otherwise
        """
        return file_path.exists()

    @staticmethod
    async def copy(source: Path, destination: Path) -> bool:
        """Copies a file asynchronously.

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure destination directory exists
            os.makedirs(destination.parent, exist_ok=True)

            if await AsyncFileIO.exists(source):
                if source.is_file():
                    content = await AsyncFileIO.read_binary(source)
                    return await AsyncFileIO.write_binary(destination, content)
                else:
                    logger.error(f"Source {source} is not a file")
                    return False
            else:
                logger.error(f"Source file {source} does not exist")
                return False
        except Exception as e:
            logger.error(f"Error copying {source} to {destination}: {e}")
            return False

    @staticmethod
    async def read_chunked(
        file_path: Path, chunk_size: int = 8192, buffer_limit: int | None = None
    ) -> AsyncGenerator[bytes]:
        """
        Read a file in chunks to limit memory usage.

        Args:
            file_path: Path to the file to read
            chunk_size: Size of each chunk in bytes
            buffer_limit: Maximum number of chunks to buffer (None for no limit)

        Yields:
            Chunks of file content as bytes
        """
        if SafeFileHandler.should_ignore(file_path):
            logger.info(f"Skipping ignored file: {file_path}")
            return

        try:
            if buffer_limit:
                semaphore = asyncio.Semaphore(buffer_limit)

            async with aiofiles.open(file_path, "rb") as f:
                while True:
                    if buffer_limit:
                        await semaphore.acquire()

                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break

                    yield chunk

                    if buffer_limit:
                        semaphore.release()
        except Exception as e:
            logger.error(f"Error reading {file_path} in chunks: {e}")

    @staticmethod
    async def write_chunked(
        file_path: Path,
        content_iterator: AsyncIterable[bytes],
        buffer_limit: int | None = None,
    ) -> bool:
        """Writes content to a file asynchronously in chunks.

        Args:
            file_path: Path to the file to write
            content_iterator: Iterator of content chunks to write
            buffer_limit: Maximum number of chunks to buffer at once

        Returns:
            True if successful, False otherwise
        """
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(file_path, "wb") as f:
                async for chunk in content_iterator:
                    await f.write(chunk)
                    if buffer_limit:
                        await asyncio.sleep(0)
            return True
        except Exception as e:
            logger.error(f"Error writing to {file_path}: {e}")
            return False

    @staticmethod
    async def copy_chunked(
        source: Path,
        destination: Path,
        chunk_size: int = 8192,
        buffer_limit: int | None = None,
    ) -> bool:
        """
        Copy a file in chunks to limit memory usage.

        Args:
            source: Source file path
            destination: Destination file path
            chunk_size: Size of each chunk in bytes
            buffer_limit: Maximum number of chunks to buffer (None for no limit)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure destination directory exists
            os.makedirs(destination.parent, exist_ok=True)

            if not await AsyncFileIO.exists(source):
                logger.error(f"Source file {source} does not exist")
                return False

            if not source.is_file():
                logger.error(f"Source {source} is not a file")
                return False

            async for chunk in AsyncFileIO.read_chunked(
                source, chunk_size, buffer_limit
            ):
                if not await AsyncFileIO.write_chunked(
                    destination,
                    AsyncFileIO.list_to_async_iterable([chunk]),
                    buffer_limit,
                ):
                    return False

            return True
        except Exception as e:
            logger.error(f"Error copying {source} to {destination}: {e}")
            return False

    @staticmethod
    async def process_large_file(
        file_path: Path,
        processor: Callable[[bytes], Any],
        chunk_size: int = 8192,
        buffer_limit: int | None = None,
    ) -> bool:
        """
        Process a large file in chunks with a custom processor function.

        Args:
            file_path: Path to the file to process
            processor: Async function that processes each chunk
            chunk_size: Size of each chunk in bytes
            buffer_limit: Maximum number of chunks to buffer (None for no limit)

        Returns:
            True if successful, False otherwise
        """
        try:
            async for chunk in AsyncFileIO.read_chunked(
                file_path, chunk_size, buffer_limit
            ):
                await processor(chunk)
            return True
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return False

    @staticmethod
    async def get_file_size(file_path: Path) -> int | None:
        """
        Get file size without reading the entire file.

        Args:
            file_path: Path to the file

        Returns:
            File size in bytes or None if error
        """
        try:
            stats = await aiofiles.os.stat(file_path)
            return cast(int, stats.st_size)
        except Exception as e:
            logger.error(f"Error getting size of {file_path}: {e}")
            return None

    @staticmethod
    async def stream_append(
        file_path: Path,
        content_iterator: AsyncIterable[bytes],
        buffer_limit: int | None = None,
    ) -> bool:
        """
        Append content to a file in streaming fashion.

        Args:
            file_path: Path to the file
            content_iterator: Async iterator yielding content chunks
            buffer_limit: Maximum number of chunks to buffer (None for no limit)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(file_path.parent, exist_ok=True)

            if buffer_limit:
                semaphore = asyncio.Semaphore(buffer_limit)

            async with aiofiles.open(file_path, "ab") as f:
                async for chunk in content_iterator:
                    if buffer_limit:
                        await semaphore.acquire()

                    await f.write(chunk)

                    if buffer_limit:
                        semaphore.release()
            return True
        except Exception as e:
            logger.error(f"Error appending chunks to {file_path}: {e}")
            return False

    @staticmethod
    async def list_to_async_iterable(items: list[bytes]) -> AsyncGenerator[bytes]:
        """Converts a list to an async iterable.

        Args:
            items: List of items to convert

        Yields:
            Items from the list one by one
        """
        for item in items:
            yield item


# Create aliases for backward compatibility
AsyncFileTools = AsyncFileIO
AsyncFileReader = AsyncFileIO
