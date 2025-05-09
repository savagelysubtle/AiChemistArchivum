"""Ensures file operations remain within safe directories and ignore patterns."""

import logging
from pathlib import Path

from the_aichemist_codex.core.config import get_codex_config

logger = logging.getLogger(__name__)

# Default ignore patterns if none specified in config
DEFAULT_IGNORE_PATTERNS = {
    ".git",
    "__pycache__",
    "*.pyc",
    ".DS_Store",
    "node_modules",
    ".env",
    "venv",
    ".venv",
    ".idea",
    ".vscode",
}

# Binary file detection constants
BINARY_EXTENSIONS = {
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".tiff",
    ".webp",
    # Audio
    ".mp3",
    ".wav",
    ".ogg",
    ".m4a",
    ".flac",
    # Video
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".webm",
    # Documents
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".bz2",
    ".xz",
    # Executables
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".app",
    # Python specific
    ".pyc",
    ".pyo",
    ".pyd",
    # Other binary
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".class",
    ".jar",
}

# Number of bytes to check for binary content
BINARY_CHECK_SIZE = 8192  # 8KB
# Maximum ratio of non-text characters allowed
MAX_BINARY_RATIO = 0.3  # 30%


class SafeFileHandler:
    """Provides validation utilities to ensure safe file operations."""

    def __init__(self) -> None:
        """Initialize with configuration."""
        self._config = get_codex_config()
        self._cached_patterns: set[str] = set()
        self._cached_directories: list[Path] = []
        self._load_ignore_patterns()

    def _load_ignore_patterns(self) -> None:
        """Load and cache ignore patterns from configuration."""
        try:
            # Get configured patterns, falling back to defaults if none specified
            config_patterns = self._config.get("ignore_patterns", [])
            if not isinstance(config_patterns, (list, set)):
                logger.warning("Invalid ignore_patterns in config, using defaults")
                config_patterns = []

            # Combine with default patterns
            self._cached_patterns = set(config_patterns) | DEFAULT_IGNORE_PATTERNS
            logger.debug(f"Loaded ignore patterns: {self._cached_patterns}")

            # Load ignored directories
            ignored_dirs = self._config.get("ignored_directories", [])
            if not isinstance(ignored_dirs, (list, set)):
                logger.warning("Invalid ignored_directories in config")
                ignored_dirs = []

            # Convert to Path objects and validate
            self._cached_directories = []
            for dir_path in ignored_dirs:
                try:
                    path = Path(dir_path).resolve()
                    self._cached_directories.append(path)
                except (TypeError, ValueError) as e:
                    logger.error(f"Invalid directory path '{dir_path}': {e}")

            logger.debug(f"Loaded ignored directories: {self._cached_directories}")

        except Exception as e:
            logger.error(f"Error loading ignore patterns: {e}")
            # Fall back to defaults
            self._cached_patterns = DEFAULT_IGNORE_PATTERNS
            self._cached_directories = []

    @staticmethod
    def is_safe_path(target: Path, base: Path) -> bool:
        """
        Ensures that a target path is within the base directory.

        Args:
            target: The target path to check
            base: The base directory path

        Returns:
            bool: True if the target is within the base directory
        """
        try:
            resolved_base = base.resolve()
            resolved_target = target.resolve()
            return resolved_base in resolved_target.parents
        except (FileNotFoundError, RuntimeError) as e:
            # If there's an error resolving paths, consider it unsafe
            logger.error(f"Error resolving paths - target: {target}, base: {base}: {e}")
            return False

    def should_ignore(self, file_path: Path) -> bool:
        """
        Checks if a file should be ignored based on patterns and directories.

        Uses both the default ignore patterns and any additional patterns
        specified in the config file.

        Args:
            file_path: The path to check

        Returns:
            bool: True if the file should be ignored
        """
        try:
            # Ensure patterns are loaded
            if not self._cached_patterns:
                self._load_ignore_patterns()

            # Check file/directory name against patterns
            for pattern in self._cached_patterns:
                if file_path.match(pattern):
                    logger.debug(f"Ignoring {file_path} (matched pattern {pattern})")
                    return True
                # Check if any parent directory matches the pattern
                for part in file_path.parts:
                    if Path(part).match(pattern):
                        logger.debug(
                            f"Ignoring {file_path} (parent matched pattern {pattern})"
                        )
                        return True

            # Check against ignored directories
            try:
                resolved_path = file_path.resolve()
                for ignored_dir in self._cached_directories:
                    if (
                        ignored_dir in resolved_path.parents
                        or ignored_dir == resolved_path
                    ):
                        logger.debug(
                            f"Ignoring {file_path} (in ignored directory {ignored_dir})"
                        )
                        return True
            except (FileNotFoundError, RuntimeError) as e:
                logger.warning(f"Could not resolve path {file_path}: {e}")
                # If we can't resolve the path, check string-based matching as fallback
                for ignored_dir in self._cached_directories:
                    if str(ignored_dir) in str(file_path):
                        logger.debug(
                            f"Ignoring {file_path} (string match with {ignored_dir})"
                        )
                        return True

            return False

        except Exception as e:
            logger.error(f"Error checking ignore status for {file_path}: {e}")
            # If there's an error, be conservative and ignore the file
            return True

    @staticmethod
    def is_binary_file(file_path: Path, check_content: bool = True) -> bool:
        """
        Determines if a file is binary using both extension and content analysis.

        This method uses a two-step approach:
        1. Fast check based on file extension
        2. Optional content analysis by reading a sample of the file (if check_content=True)

        The content analysis looks for:
        - Null bytes (common in binary files)
        - High ratio of non-text characters
        - UTF-8 decoding errors

        Args:
            file_path: The path to check
            check_content: Whether to perform content analysis (default: True)

        Returns:
            bool: True if the file is considered binary
        """
        # Step 1: Quick extension check
        if file_path.suffix.lower() in BINARY_EXTENSIONS:
            return True

        # Step 2: Content analysis (if enabled and file exists)
        if check_content and file_path.is_file():
            try:
                # Read initial bytes
                with open(file_path, "rb") as f:
                    sample = f.read(BINARY_CHECK_SIZE)

                if not sample:  # Empty file
                    return False

                # Check for null bytes (common in binary files)
                if b"\x00" in sample:
                    return True

                # Count control characters (excluding whitespace)
                control_chars = sum(
                    1 for byte in sample if byte < 32 and byte not in (9, 10, 13)
                )
                if control_chars / len(sample) > MAX_BINARY_RATIO:
                    return True

                # Try UTF-8 decoding
                try:
                    sample.decode("utf-8")
                    return False
                except UnicodeDecodeError:
                    return True

            except OSError as e:
                logger.warning(
                    f"Error reading file for binary detection {file_path}: {e}"
                )
                # If we can't read the file, fall back to extension check
                return False

        return False


# Create a singleton instance for application-wide use
safe_file_handler = SafeFileHandler()
