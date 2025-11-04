"""
Manages and evaluates rules for the AIchemist Archivum.

This module will handle loading, parsing, and applying rules,
for example, to determine if files should be ignored or how
they should be processed.
"""

import logging
import re
from re import Pattern
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self

logger = logging.getLogger(__name__)


class Rule:
    """Represents a single rule with a pattern and an action."""

    def __init__(self: "Self", pattern_str: str, action: str = "ignore") -> None:
        self.pattern_str = pattern_str
        try:
            self.regex: Pattern[str] = re.compile(pattern_str, re.IGNORECASE)
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern_str}': {e}")
            # Fallback to a pattern that will likely not match anything
            self.regex = re.compile(
                r"\A(?!x)x\Z"
            )  # Matches an empty string that isn't empty
        self.action = action


class RulesEngine:
    """
    Manages and applies rules, primarily for ignoring files/directories.
    """

    def __init__(self: "Self") -> None:
        self.rules: list[Rule] = []
        logger.info("RulesEngine initialized.")
        # self._load_rules() # Future: Load from a config file or persistent storage

    def _load_rules(self: "Self") -> None:
        """
        Placeholder for loading rules.
        This could load from a YAML/JSON file, a database, or environment variables.
        Example rule structure:
        rules:
          - pattern: "*.tmp"
            action: "ignore"
          - pattern: "/build/"
            action: "ignore"
        """
        pass

    def should_ignore(self: "Self", file_path: str) -> bool:
        """
        Checks if a given file path should be ignored based on loaded rules.
        Currently, only supports 'ignore' action.

        Args:
            file_path: The absolute or relative path to the file/directory.

        Returns:
            True if the path matches an 'ignore' rule, False otherwise.
        """
        # Normalize path to handle OS differences (e.g., \ vs /)
        # and ensure consistent matching, especially for directory patterns.
        normalized_path = file_path.replace("\\", "/")

        for rule in self.rules:
            if rule.action == "ignore":
                # For directory patterns ending with /, ensure we match paths within that dir
                if rule.pattern_str.endswith("/"):
                    if rule.regex.match(normalized_path) or rule.regex.match(
                        normalized_path + "/"
                    ):
                        logger.debug(
                            f"Path '{file_path}' ignored by rule: {rule.pattern_str}"
                        )
                        return True
                elif rule.regex.search(normalized_path):
                    logger.debug(
                        f"Path '{file_path}' ignored by rule: {rule.pattern_str}"
                    )
                    return True
        return False

    def add_rule(self: "Self", rule_pattern: str, action: str = "ignore") -> None:
        """
        Adds a new rule to the engine.

        Args:
            rule_pattern: The regex pattern for the rule.
            action: The action to take (e.g., "ignore"). Defaults to "ignore".
        """
        if not rule_pattern:
            logger.warning("Attempted to add an empty rule pattern. Skipping.")
            return

        new_rule = Rule(rule_pattern, action)
        # Avoid adding duplicate rules if pattern and action are the same
        if any(
            r.pattern_str == new_rule.pattern_str and r.action == new_rule.action
            for r in self.rules
        ):
            logger.debug(
                f"Rule with pattern '{rule_pattern}' and action '{action}' already exists. Skipping."
            )
        else:
            self.rules.append(new_rule)
            logger.info(f"Added rule: Pattern='{rule_pattern}', Action='{action}'")

    def clear_rules(self: "Self") -> None:
        """Removes all rules from the engine."""
        self.rules = []
        logger.info("All rules cleared from RulesEngine.")

    def get_rules(self: "Self") -> list[dict[str, str]]:
        """Returns a list of current rules (pattern and action)."""
        return [
            {"pattern": rule.pattern_str, "action": rule.action} for rule in self.rules
        ]


__all__ = ["RulesEngine"]
