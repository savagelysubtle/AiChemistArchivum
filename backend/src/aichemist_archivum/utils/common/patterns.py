"""Manages file ignore patterns for The Aichemist Codex."""

import fnmatch
import os

from aichemist_archivum.config import config


class PatternMatcher:
    """Checks if files should be ignored based on configured patterns."""

    def __init__(self) -> None:
        # Safely get ignore patterns with a default empty list
        ignore_patterns_raw = config.get("ignore_patterns") if config else []
        # Ensure we have a list of strings
        if ignore_patterns_raw and isinstance(ignore_patterns_raw, list):
            ignore_patterns: list[str] = [str(p) for p in ignore_patterns_raw]
            self.ignore_patterns = set(ignore_patterns)
        else:
            self.ignore_patterns: set[str] = set()

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
