"""Versioning operations for the AIchemist Codex.

This module provides functionality for file versioning, including version creation,
retrieval, and rollback capabilities.
"""

from .diff_engine import DiffEngine, DiffFormat, DiffResult
from .metadata import RollbackResult, VersionGraph, VersionMetadata, VersionType

# Import rollback components
from .rollback.engine import (
    RollbackEngine,
    RollbackSpec,
    RollbackStrategy,
    rollback_engine,
)
from .rollback.transaction import (
    TransactionManager,
    TransactionMetadata,
    TransactionState,
    transaction_manager,
)
from .version_manager import VersionManager, version_manager

__all__ = [
    # Core versioning
    "VersionManager",
    "version_manager",
    "VersionMetadata",
    "VersionType",
    "VersionGraph",
    # Diff engine
    "DiffEngine",
    "DiffFormat",
    "DiffResult",
    # Rollback
    "RollbackEngine",
    "rollback_engine",
    "RollbackSpec",
    "RollbackStrategy",
    "RollbackResult",
    # Transactions
    "TransactionManager",
    "transaction_manager",
    "TransactionMetadata",
    "TransactionState",
]
