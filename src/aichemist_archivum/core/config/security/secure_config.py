"""Provides secure configuration management with encryption."""

import base64
import json
import logging
import os
import platform
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from the_aichemist_codex.infrastructure.config.settings import determine_project_root

# Define DATA_DIR based on project root
PROJECT_ROOT = determine_project_root()
DATA_DIR = PROJECT_ROOT / "data"

logger = logging.getLogger(__name__)


class SecureConfigManager:
    """Manages secure storage and retrieval of sensitive configuration values."""

    def __init__(self, config_file: Path = DATA_DIR / "secure_config.enc") -> None:
        """
        Initialize secure configuration manager.

        Args:
            config_file: Path to the encrypted configuration file
        """
        self.config_file = config_file
        self._config: dict[str, Any] = {}

        # Get encryption key and initialize Fernet
        self._key = self._get_or_create_key()
        if self._key:
            self._fernet = Fernet(self._key)
            # Load config after Fernet is initialized
            self._config = self._load_config()
        else:
            logger.error("Failed to initialize encryption key")
            self._fernet = None

    def _get_or_create_key(self) -> bytes | None:
        """
        Get or create encryption key from environment or key file.

        Returns:
            bytes: The encryption key or None if key creation/retrieval failed
        """
        key_file = DATA_DIR / ".encryption_key"

        # Try to get key from environment
        env_key = os.environ.get("AICHEMIST_ENCRYPTION_KEY")
        if env_key:
            try:
                key = base64.urlsafe_b64decode(env_key)
                logger.debug("Using encryption key from environment")
                return key
            except base64.binascii.Error as e:
                logger.error(f"Invalid base64 encoding in environment key: {e}")
            except Exception as e:
                logger.error(f"Error processing environment key: {e}")

        # Try to load from key file
        if key_file.exists():
            try:
                with open(key_file, "rb") as f:
                    key = f.read()
                logger.debug("Using encryption key from file")
                return key
            except OSError as e:
                logger.error(f"OS error reading key file: {e}")
            except Exception as e:
                logger.error(f"Unexpected error reading key file: {e}")

        # Generate new key
        logger.info("Generating new encryption key")
        try:
            key = Fernet.generate_key()

            # Ensure directory exists
            key_file.parent.mkdir(parents=True, exist_ok=True)

            # Save new key with appropriate permissions
            self._save_key_with_permissions(key_file, key)

            return key
        except Exception as e:
            logger.error(f"Failed to generate or save new key: {e}")
            return None

    def _save_key_with_permissions(self, key_file: Path, key: bytes) -> None:
        """
        Save encryption key with appropriate permissions for the platform.

        Args:
            key_file: Path to save the key
            key: The encryption key to save
        """
        try:
            # Write the key first
            with open(key_file, "wb") as f:
                f.write(key)

            if platform.system() != "Windows":
                # Unix-like systems: use chmod
                os.chmod(key_file, 0o600)
            else:
                # Windows: try to use pywin32 if available
                try:
                    import ntsecuritycon as con
                    import win32con
                    import win32security

                    username = os.environ.get("USERNAME")
                    if not username:
                        raise ValueError("Could not determine current username")

                    sd = win32security.GetFileSecurity(
                        str(key_file), win32security.DACL_SECURITY_INFORMATION
                    )
                    dacl = win32security.ACL()

                    user_sid, _, _ = win32security.LookupAccountName(None, username)
                    dacl.AddAccessAllowedAce(
                        win32security.ACL_REVISION,
                        con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE,
                        user_sid,
                    )

                    sd.SetSecurityDescriptorDacl(1, dacl, 0)
                    win32security.SetFileSecurity(
                        str(key_file), win32security.DACL_SECURITY_INFORMATION, sd
                    )
                    logger.debug("Set Windows file permissions successfully")
                except ImportError:
                    logger.warning(
                        "pywin32 not installed, cannot set secure Windows file permissions"
                    )
                except Exception as e:
                    logger.error(f"Failed to set Windows file permissions: {e}")

        except OSError as e:
            logger.error(f"OS error saving key file: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving key file: {e}")
            raise

    def _load_config(self) -> dict[str, Any]:
        """
        Load and decrypt configuration from file.

        Returns:
            dict: The decrypted configuration or empty dict if loading fails
        """
        if not self._fernet:
            logger.error("Cannot load config: Fernet not initialized")
            return {}

        if not self.config_file.exists():
            logger.debug("Config file does not exist, using empty configuration")
            return {}

        try:
            with open(self.config_file, "rb") as f:
                encrypted_data = f.read()

            if not encrypted_data:
                logger.debug("Empty config file, using empty configuration")
                return {}

            try:
                decrypted_data = self._fernet.decrypt(encrypted_data)
                loaded_config = json.loads(decrypted_data)

                if not isinstance(loaded_config, dict):
                    logger.error("Decrypted config is not a dictionary")
                    return {}

                logger.debug("Successfully loaded secure configuration")
                return loaded_config

            except InvalidToken:
                logger.error("Invalid or corrupted encrypted data")
                return {}
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in decrypted data: {e}")
                return {}

        except OSError as e:
            logger.error(f"OS error reading config file: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading config: {e}")

        return {}

    def _save_config(self) -> bool:
        """
        Encrypt and save configuration to file.

        Returns:
            bool: True if save was successful, False otherwise
        """
        if not self._fernet:
            logger.error("Cannot save config: Fernet not initialized")
            return False

        try:
            # Ensure the config is serializable
            json_data = json.dumps(self._config)
            encrypted_data = self._fernet.encrypt(json_data.encode())

            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # Write encrypted data
            with open(self.config_file, "wb") as f:
                f.write(encrypted_data)

            # Set secure permissions on Unix-like systems
            if platform.system() != "Windows":
                os.chmod(self.config_file, 0o600)

            logger.debug("Successfully saved secure configuration")
            return True

        except json.JSONEncodeError as e:
            logger.error(f"Failed to serialize config data: {e}")
        except OSError as e:
            logger.error(f"OS error saving config file: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving config: {e}")

        return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value

        Returns:
            bool: True if value was set and saved successfully
        """
        try:
            # Verify value is JSON serializable before setting
            json.dumps({key: value})

            self._config[key] = value
            return self._save_config()

        except (TypeError, json.JSONEncodeError) as e:
            logger.error(f"Cannot set non-serializable value for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete a configuration value.

        Args:
            key: Configuration key

        Returns:
            True if key existed and was deleted, False otherwise
        """
        if key in self._config:
            del self._config[key]
            return self._save_config()
        return False

    def get_all(self) -> dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            Dictionary containing all configuration values
        """
        return self._config.copy()

    def clear(self) -> bool:
        """
        Clear all configuration values.

        Returns:
            bool: True if clear and save was successful
        """
        self._config.clear()
        return self._save_config()

    def rotate_key(self) -> bool:
        """
        Generate a new encryption key and re-encrypt configuration.

        Returns:
            bool: True if key rotation was successful
        """
        if not self._fernet:
            logger.error("Cannot rotate key: Fernet not initialized")
            return False

        try:
            # Save current config
            current_config = self._config.copy()

            # Generate new key
            new_key = Fernet.generate_key()
            new_fernet = Fernet(new_key)

            # Save new key
            key_file = DATA_DIR / ".encryption_key"
            self._save_key_with_permissions(key_file, new_key)

            # Update instance variables
            self._key = new_key
            self._fernet = new_fernet
            self._config = current_config

            # Save with new key
            if self._save_config():
                logger.info("Successfully rotated encryption key")
                return True
            else:
                logger.error("Failed to save config with new key")
                return False

        except Exception as e:
            logger.error(f"Failed to rotate encryption key: {e}")
            return False


# Create a singleton instance for application-wide use
# secure_config = SecureConfigManager() # REMOVE THIS LINE
