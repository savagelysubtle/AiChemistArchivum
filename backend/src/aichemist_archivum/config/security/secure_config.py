"""Provides secure configuration management with encryption."""

import base64
import json
import logging
import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..settings import determine_project_root

# Define DATA_DIR based on project root
PROJECT_ROOT = determine_project_root()
DATA_DIR = PROJECT_ROOT / "data"

if TYPE_CHECKING:
    from typing import Self

logger = logging.getLogger(__name__)

# Environment variable to specify a custom encryption key
ENV_KEY_NAME = "AICHEMIST_CODEX_SECURE_KEY"
# Default filename for the key if not provided by env var
DEFAULT_KEY_FILENAME = ".codex_secure.key"


class SecureConfigManager:
    """Manages secure storage and retrieval of sensitive configuration values."""

    def __init__(
        self: "Self", config_file: Path = DATA_DIR / "secure_config.enc"
    ) -> None:
        """
        Initialize secure configuration manager.

        Args:
            config_file: Path to the encrypted configuration file.
                         Defaults to 'secure_config.enc' in the DATA_DIR.
        """
        self.config_file = config_file
        self.key_file = config_file.parent / DEFAULT_KEY_FILENAME
        self._fernet: Fernet | None = None
        self._config: dict[str, Any] = {}

        key = self._get_or_create_key()
        if key:
            self._fernet = Fernet(key)
            self._config = self._load_config()
        else:
            logger.error(
                "Failed to obtain or create encryption key. Secure config will not be available."
            )
            self._fernet = None  # Ensure fernet is None if key failed

    def _get_or_create_key(self: "Self") -> bytes | None:
        """
        Get or create encryption key from environment or key file.
        Priority: ENV_KEY_NAME -> key_file.
        If neither exists, a new key is generated and saved to key_file.
        """
        env_key = os.environ.get(ENV_KEY_NAME)
        if env_key:
            try:
                key = base64.urlsafe_b64decode(env_key.encode())
                if (
                    len(key) == 32
                ):  # Fernet keys must be 32 url-safe base64-encoded bytes
                    logger.info(
                        f"Using encryption key from environment variable {ENV_KEY_NAME}."
                    )
                    # Optionally, persist this key to key_file if it doesn't exist,
                    # but be cautious about security implications.
                    return key
                else:
                    logger.warning(
                        f"Key from {ENV_KEY_NAME} is not 32 bytes after decoding. Ignoring."
                    )
            except Exception as e:
                logger.warning(
                    f"Error decoding key from {ENV_KEY_NAME}: {e}. Ignoring."
                )

        if self.key_file.exists():
            try:
                with self.key_file.open("rb") as f:
                    key = f.read()
                if len(key) == 32:
                    logger.info(f"Loaded encryption key from {self.key_file}.")
                    return key
                else:
                    logger.warning(
                        f"Key from {self.key_file} is not 32 bytes. A new key will be generated."
                    )
            except OSError as e:
                logger.error(
                    f"Error reading key file {self.key_file}: {e}. A new key will be generated."
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error reading key file {self.key_file}: {e}. A new key will be generated."
                )

        # If no key found or key is invalid, generate a new one
        try:
            new_key = Fernet.generate_key()
            self._save_key_with_permissions(self.key_file, new_key)
            logger.info(f"Generated and saved new encryption key to {self.key_file}.")
            return new_key
        except OSError as e:
            logger.error(f"Failed to save new key to {self.key_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error generating/saving new key: {e}")
        return None

    def _save_key_with_permissions(self: "Self", key_file: Path, key: bytes) -> None:
        """
        Save encryption key with appropriate permissions for the platform.
        - Windows: Restrict to owner.
        - POSIX: Set to 0o600 (owner read/write only).
        """
        try:
            # Create parent directory if it doesn't exist
            key_file.parent.mkdir(parents=True, exist_ok=True)

            with key_file.open("wb") as f:
                f.write(key)

            if platform.system() == "Windows":
                try:
                    import ntsecuritycon as con  # pyright: ignore [reportMissingImports]
                    import win32security  # pyright: ignore [reportMissingImports]

                    user, _domain, _type = win32security.LookupAccountName(
                        "", os.getlogin()
                    )
                    sd = win32security.GetFileSecurity(
                        str(key_file), win32security.DACL_SECURITY_INFORMATION
                    )
                    dacl = win32security.ACL()
                    dacl.AddAccessAllowedAce(
                        win32security.ACL_REVISION,
                        con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE,
                        user,
                    )
                    sd.SetSecurityDescriptorDacl(1, dacl, 0)
                    win32security.SetFileSecurity(
                        str(key_file), win32security.DACL_SECURITY_INFORMATION, sd
                    )
                    logger.debug(
                        f"Set restricted permissions for key file on Windows: {key_file}"
                    )
                except ImportError:
                    logger.warning(
                        "pywin32 not installed, cannot set secure Windows file permissions for key file."
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to set secure permissions for key file on Windows: {e}"
                    )
            else:  # POSIX-like systems
                os.chmod(key_file, 0o600)
                logger.debug(f"Set 0o600 permissions for key file on POSIX: {key_file}")

        except OSError as e:
            logger.error(f"Error saving key file {key_file} with permissions: {e}")
            raise  # Re-raise to indicate failure in key saving
        except Exception as e:
            logger.error(
                f"Unexpected error saving key file {key_file} with permissions: {e}"
            )
            raise  # Re-raise

    def _load_config(self: "Self") -> dict[str, Any]:
        """
        Load and decrypt configuration from file.
        Returns an empty dict if decryption fails or file doesn't exist.
        """
        if not self._fernet:
            logger.warning("Encryption key not available. Cannot load secure config.")
            return {}
        if not self.config_file.exists():
            logger.debug(
                f"Secure config file not found: {self.config_file}. Returning empty config."
            )
            return {}

        try:
            with self.config_file.open("rb") as f:
                encrypted_data = f.read()
            if not encrypted_data:
                logger.debug(
                    f"Secure config file {self.config_file} is empty. Returning empty config."
                )
                return {}

            decrypted_data = self._fernet.decrypt(encrypted_data)
            config_dict = json.loads(decrypted_data.decode("utf-8"))
            if isinstance(config_dict, dict):
                logger.info(f"Secure configuration loaded from {self.config_file}.")
                return config_dict
            else:
                logger.error(
                    f"Decrypted secure config from {self.config_file} is not a dictionary. Corrupted?"
                )
                return {}
        except InvalidToken:
            logger.error(
                f"Failed to decrypt secure config file {self.config_file}. Key mismatch or corrupted file?"
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"Error decoding JSON from decrypted secure config {self.config_file}: {e}"
            )
        except OSError as e:
            logger.error(f"Error reading secure config file {self.config_file}: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error loading secure config {self.config_file}: {e}"
            )
        return {}

    def _save_config(self: "Self") -> bool:
        """
        Encrypt and save configuration to file.
        Returns True on success, False on failure.
        """
        if not self._fernet:
            logger.error("Encryption key not available. Cannot save secure config.")
            return False

        try:
            # Create parent directory if it doesn't exist
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            config_json = json.dumps(self._config, indent=4)
            encrypted_data = self._fernet.encrypt(config_json.encode("utf-8"))

            with self.config_file.open("wb") as f:
                f.write(encrypted_data)
            logger.info(f"Secure configuration saved to {self.config_file}.")
            # Set permissions for the config file itself, similar to the key file
            if platform.system() == "Windows":
                # Apply similar DACL logic as for the key file if desired
                pass  # Placeholder for Windows config file permissions
            else:
                os.chmod(self.config_file, 0o600)
            return True
        except TypeError as e:
            logger.error(
                f"Error serializing secure config to JSON: {e}. Check for non-serializable data."
            )
        except OSError as e:
            logger.error(f"Error writing secure config file {self.config_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving secure config: {e}")
        return False

    def get(self: "Self", key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: The key of the value to retrieve.
            default: The default value to return if the key is not found.

        Returns:
            The configuration value or the default.
        """
        if not self._fernet:
            logger.warning("Secure config is not available. Returning default.")
            return default
        return self._config.get(key, default)

    def set(self: "Self", key: str, value: Any) -> bool:
        """
        Set a configuration value.
        The change is immediately persisted to the encrypted file.

        Args:
            key: The key of the value to set.
            value: The value to set. Must be JSON-serializable.

        Returns:
            True if successful, False otherwise.
        """
        if not self._fernet:
            logger.error("Secure config is not available. Cannot set value.")
            return False
        try:
            # Test serializability before updating in-memory and saving
            json.dumps(value)
        except TypeError as e:
            logger.error(
                f"Value for key '{key}' is not JSON-serializable: {e}. Not setting."
            )
            return False

        self._config[key] = value
        if not self._save_config():
            # Attempt to revert in-memory change if save failed, though this could be complex
            # For simplicity, here we just log the failure. A more robust system might handle this.
            logger.error(
                f"Failed to save secure config after setting key '{key}'. In-memory version updated, but disk is not."
            )
            return False
        return True

    def delete(self: "Self", key: str) -> bool:
        """
        Delete a configuration value.
        The change is immediately persisted.

        Args:
            key: The key to delete.

        Returns:
            True if key was present and deleted successfully, False otherwise.
        """
        if not self._fernet:
            logger.error("Secure config is not available. Cannot delete key.")
            return False
        if key in self._config:
            del self._config[key]
            return self._save_config()
        return False  # Key not found

    def get_all(self: "Self") -> dict[str, Any]:
        """
        Get all configuration values.

        Returns:
            A copy of the configuration dictionary.
        """
        if not self._fernet:
            logger.warning("Secure config is not available. Returning empty dict.")
            return {}
        return self._config.copy()

    def clear(self: "Self") -> bool:
        """
        Clear all configuration values.
        Persists the empty configuration.

        Returns:
            True if successful, False otherwise.
        """
        if not self._fernet:
            logger.error("Secure config is not available. Cannot clear.")
            return False
        self._config = {}
        return self._save_config()

    def rotate_key(self: "Self") -> bool:
        """
        Generate a new encryption key and re-encrypt configuration.
        This is a sensitive operation.
        The old key file is overwritten.

        Returns:
            True if successful, False otherwise.
        """
        if not self._fernet:
            logger.error("Initial encryption key not available. Cannot rotate key.")
            return False

        logger.warning(
            "Attempting to rotate encryption key. This will re-encrypt all secure data."
        )
        old_config = self._config.copy()  # Keep a copy of the current config

        try:
            new_key_bytes = Fernet.generate_key()
            self._save_key_with_permissions(self.key_file, new_key_bytes)
            self._fernet = Fernet(new_key_bytes)  # Switch to the new key
            self._config = (
                old_config  # Restore the config to be re-encrypted with the new key
            )
            if self._save_config():
                logger.info(
                    "Encryption key rotated and secure config re-encrypted successfully."
                )
                return True
            else:
                logger.error(
                    "Failed to save config with new key during key rotation. CRITICAL: Config might be in an inconsistent state."
                )
                # Attempt to restore old key? This is tricky and risky.
                # For now, we log a critical error.
                return False
        except Exception as e:
            logger.error(
                f"Error during key rotation: {e}. CRITICAL: Secure config state may be compromised."
            )
            return False


# Helper to derive a key from a password (example, not directly used by Fernet automatically)
# Fernet expects a 32-byte key. This shows how one might derive it.
def derive_key_from_password(password: str, salt: bytes, length: int = 32) -> bytes:
    """Derive a key from a password using PBKDF2HMACSHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=100_000,  # NIST recommended minimum
    )
    return kdf.derive(password.encode())


# Create a singleton instance for application-wide use
# secure_config = SecureConfigManager() # REMOVE THIS LINE
