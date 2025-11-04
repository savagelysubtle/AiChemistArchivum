"""Versioning operations for the AIchemist Codex.

This module provides functionality for file versioning, including version creation,
retrieval, and rollback capabilities.
"""

from .diff_engine import DiffEngine, DiffFormat, DiffResult
from .metadata import RollbackResult, VersionGraph, VersionMetadata, VersionType

# Import rollback components from services
try:
    from aichemist_archivum.services.rollback_engine import (
        RollbackEngine,
        RollbackSpec,
        RollbackStrategy,
        rollback_engine,
    )
    from aichemist_archivum.services.rollback_transaction import (
        TransactionManager,
        TransactionMetadata,
        TransactionState,
        transaction_manager,
    )
except ImportError:
    # Rollback functionality not yet available
    RollbackEngine = None  # type: ignore
    RollbackSpec = None  # type: ignore
    RollbackStrategy = None  # type: ignore
    rollback_engine = None  # type: ignore
    TransactionManager = None  # type: ignore
    TransactionMetadata = None  # type: ignore
    TransactionState = None  # type: ignore
    transaction_manager = None  # type: ignore
try:
    from aichemist_archivum.services.versioning_service import (
        VersionManager,
        version_manager,
    )
except ImportError:
    # Version manager not yet available
    VersionManager = None  # type: ignore
    version_manager = None  # type: ignore

__all__ = [
    # Diff engine
    "DiffEngine",
    "DiffFormat",
    "DiffResult",
    # Rollback
    "RollbackEngine",
    "RollbackResult",
    "RollbackSpec",
    "RollbackStrategy",
    # Transactions
    "TransactionManager",
    "TransactionMetadata",
    "TransactionState",
    "VersionGraph",
    # Core versioning
    "VersionManager",
    "VersionMetadata",
    "VersionType",
    "rollback_engine",
    "transaction_manager",
    "version_manager",
]
