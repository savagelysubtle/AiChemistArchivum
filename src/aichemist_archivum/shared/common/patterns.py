"""Manages file ignore patterns for The Aichemist Codex."""

import fnmatch
import os

from the_aichemist_codex.infrastructure.config.loader.config_loader import config


class PatternMatcher:
    """Checks if files should be ignored based on configured patterns."""

    def __init__(self) -> None:
        self.ignore_patterns = set(config.get("ignore_patterns"))

    def add_patterns(self, patterns: set) -> None:
        """Allows dynamically adding more ignore patterns."""
        self.ignore_patterns.update(patterns)

    def should_ignore(self, path: str) -> bool:
        """Determines if a given path should be ignored."""
        norm_path = os.path.normpath(path)
        base_name = os.path.basename(norm_path)

        return any(
            fnmatch.fnmatch(base_name, pattern) or fnmatch.fnmatch(norm_path, pattern)
            for pattern in self.ignore_patterns
        )


pattern_matcher = PatternMatcher()
