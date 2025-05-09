"""Handles loading of project configuration settings."""

import logging
import sys  # Needed for is_frozen check
from pathlib import Path
from typing import Any, Optional, TypeVar, overload  # Added Optional

import yaml  # Import PyYAML

from ..security.secure_config import SecureConfigManager

# Import necessary functions/constants from settings.py
# Ensure these are correctly defined in settings.py
from ..settings import CONFIG_DIR, DATA_DIR, PROJECT_ROOT, is_frozen

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_FILENAME = "settings.yaml"
USER_CONFIG_FILENAME = "settings.yaml"
SECURE_CONFIG_FILENAME = "secure_config.enc"

T = TypeVar("T")  # Define TypeVar

# Global instance cache for the factory pattern
_config_instance: Optional["CodexConfig"] = None


class CodexConfig:
    """
    Loads configuration settings for The Aichemist Codex from YAML files
    and secure storage.
    """

    def __init__(self) -> None:
        """Initialize and load configuration from default, user, and secure files."""
        self.settings: dict[str, Any] = {}
        self._secure_manager = SecureConfigManager(
            config_file=DATA_DIR / SECURE_CONFIG_FILENAME
        )
        self._load_configuration()

    def _get_default_config_path(self) -> Path | None:
        """Get the path to the default configuration file."""
        if is_frozen():
            try:
                if getattr(sys, "frozen", False):
                    base_path = Path(sys.executable).parent
                    default_path = base_path / "config" / DEFAULT_CONFIG_FILENAME
                    if default_path.exists():
                        logger.debug(f"Found bundled default config: {default_path}")
                        return default_path
            except OSError as e:
                logger.error(
                    f"OS error accessing bundled config path: {e}", exc_info=True
                )
                return None
            except Exception as e:
                logger.error(
                    f"Unexpected error determining bundled config path: {e}",
                    exc_info=True,
                )
                return None
        else:
            # When running from source, use config dir relative to project root
            default_path = PROJECT_ROOT / "config" / DEFAULT_CONFIG_FILENAME
            if default_path.exists():
                logger.debug(f"Found source default config: {default_path}")
                return default_path

        logger.warning(f"Default config file not found: {DEFAULT_CONFIG_FILENAME}")
        return None

    def _get_user_config_path(self) -> Path:
        """Get the path to the user-specific configuration file."""
        # CONFIG_DIR from settings.py already uses platformdirs when frozen
        user_path = CONFIG_DIR / USER_CONFIG_FILENAME
        logger.debug(f"Checking for user config at: {user_path}")
        return user_path

    def _load_yaml_file(self, file_path: Path | None) -> dict[str, Any]:
        """Safely load a YAML file."""
        if not file_path or not file_path.exists():
            return {}

        try:
            with file_path.open("r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if isinstance(content, dict):
                    logger.debug(f"Successfully loaded config from: {file_path}")
                    return content
                else:
                    logger.warning(
                        f"Config file is not a valid dictionary: {file_path}"
                    )
                    return {}
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error in {file_path}: {e}", exc_info=True)
        except OSError as e:
            logger.error(f"OS error reading {file_path}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error loading {file_path}: {e}", exc_info=True)
        return {}

    def _merge_configs(self, base: dict, updates: dict) -> dict:
        """Recursively merge update dict into base dict."""
        merged = base.copy()
        for key, value in updates.items():
            if (
                isinstance(value, dict)
                and key in merged
                and isinstance(merged[key], dict)
            ):
                # If both values are dicts, recurse
                merged[key] = self._merge_configs(merged[key], value)
            else:
                # Otherwise, update the value in merged
                merged[key] = value
        return merged

    def _load_configuration(self) -> None:
        """Loads default, user, and secure configurations and merges them."""
        # 1. Load bundled/default config
        default_config_path = self._get_default_config_path()
        default_settings = self._load_yaml_file(default_config_path)

        # 2. Load user-specific config
        user_config_path = self._get_user_config_path()
        user_settings = self._load_yaml_file(user_config_path)

        # 3. Load secure config using the manager's internal load logic
        # Access the protected member for initial load; manager handles decryption
        secure_settings = self._secure_manager._load_config()

        # 4. Merge: Defaults -> User -> Secure (Secure settings override others)
        merged_config = self._merge_configs(default_settings, user_settings)
        self.settings = self._merge_configs(merged_config, secure_settings)

        # 5. Inject dynamic paths (if not already set by user/secure)
        # Ensure RollbackManager can find data_dir via config.get()
        if "data_dir" not in self.settings:
            self.settings["data_dir"] = str(DATA_DIR)
            logger.debug(f"Injected dynamic data_dir: {DATA_DIR}")
        else:
            logger.debug(
                f"Using data_dir from config file: {self.settings['data_dir']}"
            )

        logger.info("Configuration loaded (Default -> User -> Secure).")
        logger.debug(f"Final configuration keys: {list(self.settings.keys())}")

    @overload
    def get(self, key: str, default: T) -> T: ...

    @overload
    def get(self, key: str, default: None = None) -> Any: ...

    def get(self, key: str, default: T | None = None) -> T | Any:
        """Retrieve a configuration setting using dot notation for nested keys."""
        keys = key.split(".")
        value = self.settings
        try:
            for k in keys:
                if isinstance(value, dict):
                    value = value[k]
                else:
                    # Handle case where intermediate key is not a dict
                    logger.warning(f"Config key '{key}' path invalid at '{k}'.")
                    return default
            # Attempt to return the value found, which could be Any
            # Explicitly ignore Any return type for this dynamic loading case
            return value  # type: ignore[no-any-return]
        except KeyError:
            # Key not found, return the provided default (T | None)
            logger.debug(f"Config key '{key}' not found, returning default: {default}")
            return default
        except Exception:
            logger.error(f"Error accessing config key '{key}'", exc_info=True)
            # Return the provided default (T | None) on other errors
            return default

    # ADD METHODS FOR SECURE CONFIG INTERACTION
    def get_secure(self, key: str, default: Any = None) -> Any:
        """Get a securely stored configuration value."""
        # Delegate to SecureConfigManager instance
        return self._secure_manager.get(key, default)

    def set_secure(self, key: str, value: Any) -> None:
        """Set a secure configuration value."""
        # Delegate to SecureConfigManager instance and reload main config
        self._secure_manager.set(key, value)
        # Reload to reflect change in the main unified settings view
        self._load_configuration()

    def delete_secure(self, key: str) -> bool:
        """Delete a secure configuration value."""
        deleted = self._secure_manager.delete(key)
        if deleted:
            # Reload to reflect change in the main unified settings view
            self._load_configuration()
        return deleted

    def get_all_secure(self) -> dict[str, Any]:
        """Get all secure configuration values."""
        return self._secure_manager.get_all()

    def get_loaded_sources(self) -> list[str]:
        """Return a list of successfully loaded configuration sources."""
        sources = []
        default_path = self._get_default_config_path()
        user_path = self._get_user_config_path()

        if default_path and default_path.exists():
            sources.append(str(default_path))
        if user_path and user_path.exists():
            sources.append(str(user_path))
        if self._secure_manager and self._secure_manager.get_all():
            sources.append("secure_config")

        return sources


# Factory function to replace singleton
def get_codex_config() -> CodexConfig:
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
