"""Handles loading of project configuration settings."""

import logging
import sys  # Needed for is_frozen check
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, TypeVar, overload

import yaml  # Import PyYAML

from ..security.secure_config import SecureConfigManager
from ..settings import CONFIG_DIR, DATA_DIR, is_frozen

# Default config file constant
DEFAULT_CONFIG_FILE = "config.yaml"

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Define TypeVar

# Global instance cache for the factory pattern
_config_instance: Optional["CodexConfig"] = None

if TYPE_CHECKING:
    from typing import Self


class CodexConfig:
    """
    Loads configuration settings for The Aichemist Codex from YAML files
    and secure storage.
    """

    def __init__(self: "Self") -> None:
        """Initialize and load configuration from default, user, and secure files."""
        self.settings: dict[str, Any] = {}
        self._secure_manager = SecureConfigManager(DATA_DIR / "secure_app_config.enc")
        self._loaded_sources: list[str] = []
        self._load_configuration()

    def _get_default_config_path(self: "Self") -> Path | None:
        """Get the path to the default configuration file."""
        if is_frozen():
            # In a frozen app, default config is bundled
            # Assuming it's in the same directory as the executable or a 'config' subdir
            exe_dir = Path(sys.executable).parent
            frozen_default_path = exe_dir / DEFAULT_CONFIG_FILE
            if frozen_default_path.exists():
                return frozen_default_path
            frozen_default_path_subdir = exe_dir / "config" / DEFAULT_CONFIG_FILE
            if frozen_default_path_subdir.exists():
                return frozen_default_path_subdir
            return None  # Or raise error if essential
        else:
            # Development: use the one in the config directory at project root
            # CONFIG_DIR now points to project_root/config/
            default_path = CONFIG_DIR / DEFAULT_CONFIG_FILE
            return default_path if default_path.exists() else None

    def _get_user_config_path(self: "Self") -> Path:
        """Get the path to the user-specific configuration file."""
        # CONFIG_DIR from settings.py already uses platformdirs when frozen
        # or a local path for development.
        user_path = CONFIG_DIR / "user_config.yaml"
        return user_path

    def _load_yaml_file(self: "Self", file_path: Path | None) -> dict[str, Any]:
        """Safely load a YAML file."""
        if not file_path or not file_path.exists():
            logger.debug(f"Configuration file not found: {file_path}")
            return {}
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                logger.warning(
                    f"Configuration file {file_path} is not a valid dictionary. Ignoring."
                )
                return {}
            logger.info(f"Successfully loaded configuration from {file_path}")
            self._loaded_sources.append(str(file_path))
            return data
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {file_path}: {e}")
        except OSError as e:
            logger.error(f"Error reading file {file_path}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading YAML file {file_path}: {e}")
        return {}

    def _merge_configs(self: "Self", base: dict, updates: dict) -> dict:
        """Recursively merge update dict into base dict."""
        merged = base.copy()
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _load_configuration(self: "Self") -> None:
        """Loads default, user, and secure configurations and merges them."""
        # 1. Load bundled/default config
        default_cfg_path = self._get_default_config_path()
        current_config = self._load_yaml_file(default_cfg_path)

        # 2. Load user-specific config and merge
        user_cfg_path = self._get_user_config_path()
        user_config = self._load_yaml_file(user_cfg_path)
        current_config = self._merge_configs(current_config, user_config)

        # 3. Load secure config and merge (secure values take precedence)
        # Note: SecureConfigManager handles its own loading internally
        secure_values = self._secure_manager.get_all()
        if secure_values:
            # Wrap secure values under a 'secure' key or merge them directly
            # Here, we merge them under a 'secure' top-level key for clarity
            # Or, you could merge them directly if preferred, carefully handling conflicts.
            # Example: current_config = self._merge_configs(current_config, {"secure": secure_values})
            # For direct merge, ensure keys don't unintentionally override non-secure ones
            # or use a specific prefix for secure keys if merging flatly.
            # current_config = self._merge_configs(current_config, secure_values) # direct merge
            self._loaded_sources.append(
                "Secure Storage"
            )  # Indicate secure storage was loaded

        self.settings = current_config
        logger.info(f"Configuration loaded and merged from: {self._loaded_sources}")

    @overload
    def get(self: "Self", key: str, default: T) -> T: ...

    @overload
    def get(self: "Self", key: str, default: None = None) -> object | None: ...

    def get(self: "Self", key: str, default: T | None = None) -> T | object | None:
        """Retrieve a configuration setting using dot notation for nested keys."""
        keys = key.split(".")
        value = self.settings
        try:
            for k in keys:
                if isinstance(value, dict):
                    value = value[k]
                else:
                    # If at any point value is not a dict, but we have more keys,
                    # it means the path is invalid.
                    logger.debug(
                        f"Config key '{key}' not found or path invalid. Returning default."
                    )
                    return default  # type: ignore[return-value]
            return value  # type: ignore[no-any-return]
        except KeyError:
            logger.debug(f"Config key '{key}' not found. Returning default.")
            return default  # type: ignore[return-value]
        except TypeError:
            # This can happen if a key exists but its value is None and we try to access a subkey
            logger.debug(
                f"Config key '{key}' path invalid (e.g. sub-key of None). Returning default."
            )
            return default  # type: ignore[return-value]

    # ADD METHODS FOR SECURE CONFIG INTERACTION
    def get_secure(
        self: "Self", key: str, default: object | None = None
    ) -> object | None:
        """Get a securely stored configuration value."""
        # Delegate to SecureConfigManager instance
        return self._secure_manager.get(key, default)

    def set_secure(self: "Self", key: str, value: object) -> None:
        """Set a secure configuration value."""
        # Delegate to SecureConfigManager instance and reload main config
        self._secure_manager.set(key, value)
        self._load_configuration()  # Reload to ensure consistency if secure values affect merged config

    def delete_secure(self: "Self", key: str) -> bool:
        """Delete a secure configuration value."""
        deleted = self._secure_manager.delete(key)
        if deleted:
            self._load_configuration()  # Reload if a value was actually deleted
        return deleted

    def get_all_secure(self: "Self") -> dict[str, Any]:
        """Get all secure configuration values."""
        return self._secure_manager.get_all()

    def get_loaded_sources(self: "Self") -> list[str]:
        """Return a list of successfully loaded configuration sources."""
        sources = []
        if self._get_default_config_path() and self._get_default_config_path().exists():  # type: ignore[misc]
            sources.append(str(self._get_default_config_path()))
        if self._get_user_config_path().exists():
            sources.append(str(self._get_user_config_path()))
        if self._secure_manager.get_all():  # Check if any secure values exist
            sources.append("Secure Storage")
        return sources


# Factory function to replace singleton
def get_codex_config() -> "CodexConfig":
    """
    Get the CodexConfig instance. Creates a new instance if none exists.

    Returns:
        CodexConfig: The configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = CodexConfig()
        logger.info("Created new CodexConfig instance")
    return _config_instance


__all__ = ["CodexConfig", "get_codex_config"]
