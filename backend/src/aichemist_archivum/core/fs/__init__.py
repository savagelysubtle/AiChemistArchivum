"""File system operations for the AIchemist Codex."""

# Updated imports reflecting refactored modules
# Temporarily commented out imports with dependency issues
# from .changes import ChangeDetector, ChangeInfo, ChangeSeverity, ChangeType
# from .directory import DirectoryManager
from .file_metadata import FileMetadata

# from .file_reader import FileReader  # Added FileReader
# from .operations import FileMover  # Added FileMover

# Parsers are now in core.parsing, not core.fs
# from ..parsing import (
#     BaseParser,
#     TextParser,
#     get_parser_for_mime_type,
# )

# Removed .rules import as it's now deprecated

# Updated __all__ list
__all__ = [
    # From file_reader.py - temporarily disabled
    # "FileReader",
    # From operations.py - temporarily disabled
    # "FileMover",
    # From parsers.py - moved to core.parsing
    # "BaseParser",
    # "TextParser",
    # "get_parser_for_mime_type",
    # From changes.py - temporarily disabled
    # "ChangeDetector",
    # "ChangeInfo",
    # "ChangeSeverity",
    # "ChangeType",
    # From directory.py - temporarily disabled
    # "DirectoryManager",
    # From file_metadata.py
    "FileMetadata",
    # From rollback.py - Note: rollback module doesn't exist in fs/
    # "OperationType",
    # "RollbackManager",
    # "rollback_manager",
]
