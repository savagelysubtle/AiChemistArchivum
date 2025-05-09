"""File system operations for the AIchemist Codex."""

# Updated imports reflecting refactored modules
from .changes import ChangeDetector, ChangeInfo, ChangeSeverity, ChangeType
from .directory import DirectoryManager
from .file_metadata import FileMetadata
from .file_reader import FileReader  # Added FileReader
from .operations import FileMover  # Added FileMover
from .parsers import (
    BaseParser,
    TextParser,  # Added get_parser
    get_parser_for_mime_type,
)
from .rollback import OperationType, RollbackManager, rollback_manager

# Removed .rules import as it's now deprecated

# Updated __all__ list
__all__ = [
    # From changes.py
    "ChangeDetector",
    "ChangeInfo",
    "ChangeSeverity",
    "ChangeType",
    # From directory.py
    "DirectoryManager",
    # From file_metadata.py
    "FileMetadata",
    # From file_reader.py
    "FileReader",
    # From operations.py
    "FileMover",
    # From parsers.py
    "BaseParser",
    "TextParser",
    "get_parser_for_mime_type",
    # From rollback.py
    "OperationType",
    "RollbackManager",
    "rollback_manager",
]
