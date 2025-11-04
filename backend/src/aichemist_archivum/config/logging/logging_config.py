"""
Logging configuration for the AIchemist Codex.

This module handles the setup and configuration of logging across the application,
supporting both dictionary-based configuration and fallback basic configuration.
"""

import logging
import logging.config
from pathlib import Path
from typing import Any

# Import necessary components from settings
# Ensure these are correctly defined in settings.py
from ..settings import DATA_DIR

LOG_FILENAME = "the_aichemist_codex.log"
LOG_FILE_PLACEHOLDER = "<<LOG_FILE_PATH>>"

logger = logging.getLogger(__name__)

# Default basic logging format
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LEVEL = logging.INFO


def _ensure_log_directory(log_path: Path) -> bool:
    """
    Ensure the log directory exists and is writable.

    Args:
        log_path: Path to the log file

    Returns:
        bool: True if directory exists and is writable, False otherwise
    """
    try:
        # Create parent directory if it doesn't exist
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Check if directory is writable by attempting to create a test file
        test_file = log_path.parent / ".test_write"
        test_file.touch()
        test_file.unlink()

        return True
    except OSError as e:
        logger.error(f"Failed to create/verify log directory {log_path.parent}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking log directory {log_path.parent}: {e}")
        return False


def _validate_handler_config(handler_config: dict[str, Any]) -> bool:
    """
    Validate a logging handler configuration.

    Args:
        handler_config: Handler configuration dictionary

    Returns:
        bool: True if configuration is valid
    """
    required_fields = {"class", "level"}

    # Check required fields
    if not all(field in handler_config for field in required_fields):
        logger.error(f"Handler config missing required fields: {required_fields}")
        return False

    # Validate level
    try:
        # Convert string level to int if needed
        if isinstance(handler_config["level"], str):
            logging.getLevelName(handler_config["level"].upper())
    except (ValueError, AttributeError) as e:
        logger.error(f"Invalid logging level in handler config: {e}")
        return False

    return True


def _update_log_path(log_config: dict[str, Any], actual_log_path: Path) -> None:
    """
    Update log file paths in the configuration dictionary.

    Args:
        log_config: Logging configuration dictionary
        actual_log_path: Actual path where log file should be written
    """
    if not isinstance(log_config, dict):
        logger.error("Invalid log_config type: expected dict")
        return

    if "handlers" not in log_config:
        logger.debug("No handlers section in logging config")
        return

    handlers = log_config["handlers"]
    if not isinstance(handlers, dict):
        logger.error("Invalid handlers section type: expected dict")
        return

    for handler_name, handler_config in handlers.items():
        if not isinstance(handler_config, dict):
            logger.warning(f"Invalid handler config for {handler_name}: expected dict")
            continue

        if "filename" not in handler_config:
            continue

        if handler_config["filename"] == LOG_FILE_PLACEHOLDER:
            # Validate handler config before updating
            if not _validate_handler_config(handler_config):
                logger.warning(f"Skipping invalid handler config: {handler_name}")
                continue

            # Ensure log directory exists and is writable
            if not _ensure_log_directory(actual_log_path):
                logger.error(f"Cannot use log file path: {actual_log_path}")
                continue

            handler_config["filename"] = str(actual_log_path)
            logger.debug(
                f"Updated log handler '{handler_name}' path: {actual_log_path}"
            )


def setup_logging(logging_config: dict[str, Any] | None = None) -> None:
    """
    Configure global logging settings.

    Args:
        logging_config: Optional dictionary with logging configuration
    """
    # 1. Set up basic logging first as a fallback
    logging.basicConfig(
        level=DEFAULT_LEVEL,
        format=DEFAULT_FORMAT,
        force=True,  # Ensure basic config is applied
    )

    if not logging_config:
        logger.info("No logging configuration provided, using basic config")
        return

    if not isinstance(logging_config, dict):
        logger.error(f"Invalid logging_config type: {type(logging_config)}")
        return

    # 2. Determine actual log file path
    actual_log_path = DATA_DIR / LOG_FILENAME

    try:
        # 3. Update log file paths in config
        _update_log_path(logging_config, actual_log_path)

        # 4. Apply the configuration
        logging.config.dictConfig(logging_config)

        # 5. Verify configuration was applied
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            raise ValueError("No handlers configured for root logger")

        logger.info(f"Logging configured successfully. Log file: {actual_log_path}")

    except ValueError as e:
        logger.error(f"Invalid logging configuration format: {e}")
        # Keep basic config active

    except OSError as e:
        logger.error(f"Failed to configure logging due to OS error: {e}")
        # Keep basic config active

    except Exception as e:
        logger.error(f"Unexpected error configuring logging: {e}", exc_info=True)
        # Keep basic config active


# Configure logging immediately when this module is imported
# setup_logging() # REMOVE THIS LINE

# You can still get a logger for this specific module if needed
# logger = logging.getLogger(__name__)
