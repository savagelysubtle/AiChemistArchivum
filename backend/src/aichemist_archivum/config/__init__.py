"""
Configuration management for the AIchemist Archivum.

Provides a unified access point to application settings loaded from
various sources (defaults, user overrides, secure storage).

Access configuration values via the `config` object (e.g., `config.get('key')`)
and secure values via `config.get_secure('key')`.
Use the `rules_engine` object for file ignore checks.
Core paths and constants are also exposed directly.
"""

import logging as _logging

# 2. Import the configuration factory function
from .loader.config_loader import get_codex_config

# 3. Import the logging setup function
from .logging.logging_config import setup_logging

# 4. Import the rules engine class
from .rules.rules_engine import RulesEngine

# 1. Import core constants/functions from settings.py first
from .settings import (
    CACHE_DIR,
    CACHE_TTL,
    CONFIG_DIR,
    DATA_DIR,
    FEATURES,
    MAX_FILE_SIZE,
    MAX_PREVIEW_LENGTH,
    MEMORY_CACHE_SIZE,
    PROJECT_ROOT,
    REGEX_MAX_COMPLEXITY,
    REGEX_MAX_RESULTS,
    REGEX_TIMEOUT_MS,
    SIMILARITY_MAX_RESULTS,
    SRC_DIR,
    determine_project_root,
    get_config_dir,
    get_data_dir,
    is_frozen,
)
from .settings import get_settings as get_static_settings

# --- Initialization Sequence ---

# Get the config instance using the factory function
_codex_config = get_codex_config()

# 5. Setup Logging using the loaded configuration
from typing import Any

_log_config_dict: dict[str, Any] | None = _codex_config.get("logging")
if not isinstance(_log_config_dict, dict):
    # This is expected before 'config init' is run - use debug level
    _logging.getLogger(__name__).debug(
        "Configuration section 'logging' not found or invalid. "
        "Logging setup will use defaults."
    )
    _log_config_dict = None

setup_logging(_log_config_dict)

# 6. Initialize the Rules Engine
rules_engine = RulesEngine()

# --- Public Interface ---

# 7. Define __all__ for the public interface of this package
__all__ = [
    # Core constants/values
    "CACHE_DIR",
    "CACHE_TTL",
    "CONFIG_DIR",
    "DATA_DIR",
    "FEATURES",
    "MAX_FILE_SIZE",
    "MAX_PREVIEW_LENGTH",
    "MEMORY_CACHE_SIZE",
    "PROJECT_ROOT",
    "REGEX_MAX_COMPLEXITY",
    "REGEX_MAX_RESULTS",
    "REGEX_TIMEOUT_MS",
    "SIMILARITY_MAX_RESULTS",
    "SRC_DIR",
    # Unified config object and factory
    "config",
    # Functions
    "determine_project_root",
    "get_codex_config",
    "get_config_dir",
    "get_data_dir",
    "get_static_settings",
    "is_frozen",
    # Rules engine instance
    "rules_engine",
]

# 8. Assign the config instance to the public name 'config'
config = _codex_config

# Log successful initialization with loaded sources
logger = _logging.getLogger(__name__)
logger.info("AIchemist Codex configuration infrastructure initialized.")
logger.info(f"Config loaded from: {config.get_loaded_sources()}")
