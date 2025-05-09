"""Rollback functionality for AIchemist Codex versioning.

This module provides rollback capabilities for file versions, including
single-file rollbacks and atomic multi-file transactions.
"""

from .engine import RollbackEngine, RollbackSpec, RollbackStrategy, rollback_engine
from .transaction import (
    TransactionManager,
    TransactionMetadata,
    TransactionState,
    transaction_manager,
)

__all__ = [
    "RollbackEngine",
    "RollbackSpec",
    "RollbackStrategy",
    "TransactionManager",
    "TransactionMetadata",
    "TransactionState",
    "rollback_engine",
    "transaction_manager",
]
