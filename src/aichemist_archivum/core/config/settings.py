"""Global settings and configuration constants."""

import logging
import os
import sys
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir, user_data_dir  # Import platformdirs

logger = logging.getLogger(__name__)

APP_NAME = "TheAIChemistCodex"
APP_AUTHOR = "AIchemist"  # Or your name/org


def is_frozen() -> bool:
    """Check if running as a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_data_dir() -> Path:
    """Get the appropriate data directory."""
    if is_frozen():
        # Use user-specific data directory when packaged
        path = Path(user_data_dir(APP_NAME, APP_AUTHOR))
        logger.debug(f"Running frozen, using user data dir: {path}")
    else:
        # Use directory relative to project root when running from source
        # (Keep or adapt your existing determine_project_root logic here for development)
        project_root = determine_project_root()  # Your existing function
        path = project_root / "data"
        logger.debug(f"Running from source, using project data dir: {path}")

    # Ensure the directory exists
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_dir() -> Path:
    """Get the appropriate config directory."""
    if is_frozen():
        # Use user-specific config directory when packaged
        path = Path(user_config_dir(APP_NAME, APP_AUTHOR))
        logger.debug(f"Running frozen, using user config dir: {path}")
    else:
        # Use project root when running from source
        project_root = determine_project_root()  # Your existing function
        path = project_root
        logger.debug(f"Running from source, using project root for config: {path}")

    path.mkdir(parents=True, exist_ok=True)
    return path


# Project root detection - more robust approach
def determine_project_root() -> Path:
    """
    Determine the project root directory using multiple methods.

    First checks for environment variable, then tries to detect based on
    repository structure, with a fallback to the parent of the src directory.

    Returns:
        Path: The determined project root directory
    """
    # Method 1: Check environment variable
    if "AICHEMIST_ROOT" in os.environ:
        path = Path(os.environ["AICHEMIST_ROOT"])
        if path.exists():
            logger.debug(f"Using project root from AICHEMIST_ROOT: {path}")
            return path
        else:
            logger.warning(
                f"AICHEMIST_ROOT set to '{os.environ['AICHEMIST_ROOT']}', but path does not exist."
            )

    # Method 2: Detect based on repository structure
    # Try to find the project root by looking for key files/directories
    current_path = Path(__file__).resolve().parent.parent.parent.parent

    # Common repository root indicators
    indicators = [
        ".git",
        "pyproject.toml",
        "setup.py",
        "README.md",
        "src/the_aichemist_codex",
    ]

    # Check the current directory and any parent directory
    check_path = current_path
    for i in range(4):  # Limit search depth
        if any((check_path / indicator).exists() for indicator in indicators):
            logger.debug(
                f"Detected project root based on indicators at depth {i}: {check_path}"
            )
            return check_path
        check_path = check_path.parent

    # Method 3: Fallback to parent of src directory
    logger.debug(
        "Project root not found via env var or indicators, attempting fallback."
    )
    fallback_path = Path(__file__).resolve().parent.parent.parent.parent
    if (fallback_path / "src").exists():
        logger.debug(f"Using fallback project root (parent of src): {fallback_path}")
        return fallback_path

    # Last resort: Use the parent of the current file's directory structure
    # This might be inaccurate if the file structure is unusual.
    last_resort_path = Path(__file__).resolve().parent.parent.parent.parent
    logger.warning(
        f"Could not reliably determine project root. Using last resort: {last_resort_path}"
    )
    return last_resort_path


# Core paths
PROJECT_ROOT = (
    determine_project_root() if not is_frozen() else Path(".")
)  # Less relevant when frozen
logger.info(f"Project root determined as: {PROJECT_ROOT}")
SRC_DIR = PROJECT_ROOT / "src"
CACHE_DIR = PROJECT_ROOT / ".cache"
DATA_DIR = get_data_dir()
CONFIG_DIR = get_config_dir()

# Feature flags
FEATURES = {
    "enable_enhanced_metadata": True,
    "enable_windows_integration": True,
    "enable_regex_search": True,
    "enable_semantic_search": True,
    "enable_similarity_search": True,
}

# Search settings
REGEX_MAX_RESULTS = 100
REGEX_MAX_COMPLEXITY = 50
REGEX_TIMEOUT_MS = 5000  # 5 seconds
SIMILARITY_MAX_RESULTS = 20

# Cache settings
CACHE_TTL = 3600  # 1 hour
MEMORY_CACHE_SIZE = 1000  # items

# File reading settings
MAX_PREVIEW_LENGTH = 500  # characters
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def get_settings() -> dict[str, Any]:
    """
    Get all settings as a dictionary.

    Returns:
        Dict containing all settings
    """
    # Get all uppercase variables from this module
    return {
        name: value
        for name, value in globals().items()
        if name.isupper() and not name.startswith("_")
    }


# --- Extraction Module Settings ---
[extraction]
metadata_manager_max_concurrent_batch = 5
tag_classifier_default_confidence_threshold = 0.6
# Add other extraction-related settings here, e.g.:
# code_extractor_patterns_path = "config/code_patterns.json"
# document_extractor_patterns_path = "config/doc_patterns.json"


# --- Security Settings ---
[security]
# Example: Specify the keyring service name
