"""Custom exceptions for The Aichemist Codex."""


class CodexError(Exception):
    """Base exception for project-related errors."""

    pass


class MaxTokenError(CodexError):
    """Raised when a file exceeds the token limit."""

    def __init__(self, file_path: str, max_tokens: int) -> None:
        super().__init__(f"{file_path} exceeds {max_tokens} token limit.")


class NotebookProcessingError(CodexError):
    """Raised when an error occurs while processing a notebook."""

    def __init__(self, file_path: str) -> None:
        super().__init__(f"Failed to process notebook: {file_path}")


class InvalidVersionError(CodexError):
    """Raised when an invalid version string is encountered."""

    pass
