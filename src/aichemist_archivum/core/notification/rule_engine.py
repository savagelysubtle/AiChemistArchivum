"""
Notification Rules Engine for The Aichemist Codex.

This module provides a flexible rules system for filtering and routing notifications
based on customizable conditions and actions.
"""

import datetime
import logging
import re
from enum import Enum
from re import Pattern
from typing import Any, TypeVar

from the_aichemist_codex.infrastructure.config.settings import determine_project_root
from the_aichemist_codex.infrastructure.notification.notification_manager import (
    Notification,
    NotificationLevel,
    NotificationType,
)
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

logger = logging.getLogger(__name__)

# Define data directory constant
DATA_DIR = determine_project_root() / "data"

# Define rules database path
RULES_DB_PATH = DATA_DIR / "notification_rules.json"

# Define a type variable for rule condition values
RuleValueType = TypeVar("RuleValueType")


class ConditionOperator(Enum):
    """Operators for rule conditions."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES_REGEX = "matches_regex"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"
    IS_NONE = "is_none"
    IS_NOT_NONE = "is_not_none"


class TimeConditionType(Enum):
    """Types of time-based conditions."""

    TIME_OF_DAY = "time_of_day"
    DAY_OF_WEEK = "day_of_week"
    DATE_RANGE = "date_range"
    FREQUENCY = "frequency"  # e.g., "no more than X in Y minutes"


class ActionType(Enum):
    """Types of actions that can be taken when a rule matches."""

    ROUTE = "route"  # Route to specific subscribers
    TRANSFORM = "transform"  # Transform the notification
    THROTTLE = "throttle"  # Apply custom throttling
    ENRICH = "enrich"  # Add additional data
    BLOCK = "block"  # Block the notification


class RuleCondition:
    """Represents a single condition in a notification rule."""

    def __init__(
        self,
        field: str,
        operator: str | ConditionOperator,
        value: Any,  # noqa: ANN401
        negate: bool = False,
    ) -> None:
        """
        Initialize a rule condition.

        Args:
            field: The notification field to check (e.g., "level", "message")
            operator: The comparison operator
            value: The value to compare against
            negate: Whether to negate the result
        """
        self.field = field
        self.operator = (
            operator
            if isinstance(operator, ConditionOperator)
            else ConditionOperator(operator)
        )
        self.value = value
        self.negate = negate
        self._regex_cache: Pattern | None = None

    async def evaluate(self, notification: Notification) -> bool:
        """
        Evaluate the condition against a notification.

        Args:
            notification: The notification to check

        Returns:
            True if the condition matches, False otherwise
        """
        # Get the field value from the notification
        field_value = self._get_field_value(notification)

        # Evaluate based on operator
        result = await self._evaluate_operator(field_value)

        # Apply negation if needed
        return not result if self.negate else result

    def _get_field_value(self, notification: Notification) -> Any:  # noqa: ANN401
        """Get a field value from the notification."""
        if self.field == "level":
            return notification.level
        elif self.field == "type":
            return notification.notification_type
        elif self.field == "message":
            return notification.message
        elif self.field == "source":
            return notification.source
        elif self.field == "timestamp":
            return notification.timestamp
        elif self.field.startswith("details."):
            # Get nested field from details
            detail_field = self.field[8:]  # Remove "details." prefix
            return notification.details.get(detail_field)
        return None

    async def _evaluate_operator(
        self,
        field_value: Any,  # noqa: ANN401
    ) -> bool:
        """Evaluate the operator against the field value."""
        if self.operator == ConditionOperator.EQUALS:
            if isinstance(field_value, Enum):
                if isinstance(self.value, str):
                    # Handle string comparison with enum
                    return (
                        field_value.name == self.value.upper()
                        or field_value.value == self.value.lower()
                    )
                return field_value == self.value
            return field_value == self.value

        elif self.operator == ConditionOperator.NOT_EQUALS:
            if isinstance(field_value, Enum):
                if isinstance(self.value, str):
                    return not (
                        field_value.name == self.value.upper()
                        or field_value.value == self.value.lower()
                    )
                return field_value != self.value
            return field_value != self.value

        elif self.operator == ConditionOperator.CONTAINS:
            if field_value is None:
                return False
            return self.value in str(field_value)

        elif self.operator == ConditionOperator.NOT_CONTAINS:
            if field_value is None:
                return True
            return self.value not in str(field_value)

        elif self.operator == ConditionOperator.STARTS_WITH:
            if field_value is None:
                return False
            return str(field_value).startswith(self.value)

        elif self.operator == ConditionOperator.ENDS_WITH:
            if field_value is None:
                return False
            return str(field_value).endswith(self.value)

        elif self.operator == ConditionOperator.MATCHES_REGEX:
            if field_value is None:
                return False
            if self._regex_cache is None:
                self._regex_cache = re.compile(self.value)
            return bool(self._regex_cache.search(str(field_value)))

        elif self.operator == ConditionOperator.GREATER_THAN:
            if field_value is None:
                return False
            return field_value > self.value

        elif self.operator == ConditionOperator.LESS_THAN:
            if field_value is None:
                return False
            return field_value < self.value

        elif self.operator == ConditionOperator.IN_LIST:
            if field_value is None:
                return False
            if isinstance(field_value, Enum):
                # Check if enum name or value is in list
                return field_value.name in self.value or field_value.value in self.value
            return field_value in self.value

        elif self.operator == ConditionOperator.NOT_IN_LIST:
            if field_value is None:
                return True
            if isinstance(field_value, Enum):
                return (
                    field_value.name not in self.value
                    and field_value.value not in self.value
                )
            return field_value not in self.value

        elif self.operator == ConditionOperator.IS_TRUE:
            return bool(field_value) is True

        elif self.operator == ConditionOperator.IS_FALSE:
            return bool(field_value) is False

        elif self.operator == ConditionOperator.IS_NONE:
            return field_value is None

        elif self.operator == ConditionOperator.IS_NOT_NONE:
            return field_value is not None

        # Default case
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
            "negate": self.negate,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuleCondition":
        """Create from dictionary (for deserialization)."""
        return cls(
            field=data["field"],
            operator=data["operator"],
            value=data["value"],
            negate=data.get("negate", False),
        )


class TimeCondition:
    """Represents a time-based condition for a notification rule."""

    def __init__(
        self,
        condition_type: str | TimeConditionType,
        value: Any,  # noqa: ANN401 - Value depends on condition type
    ) -> None:
        """
        Initialize a time condition.

        Args:
            condition_type: The type of time condition
            value: The value for the condition (format depends on type)
        """
        self.condition_type = (
            condition_type
            if isinstance(condition_type, TimeConditionType)
            else TimeConditionType(condition_type)
        )
        self.value = value

    async def evaluate(self) -> bool:
        """
        Evaluate the time condition.

        Returns:
            True if the condition matches the current time, False otherwise
        """
        now = datetime.datetime.now()

        if self.condition_type == TimeConditionType.TIME_OF_DAY:
            # Format: {"start": "HH:MM", "end": "HH:MM"}
            start_time = datetime.datetime.strptime(self.value["start"], "%H:%M").time()
            end_time = datetime.datetime.strptime(self.value["end"], "%H:%M").time()
            current_time = now.time()
            return start_time <= current_time <= end_time

        elif self.condition_type == TimeConditionType.DAY_OF_WEEK:
            # Format: [0, 1, 2, 3, 4, 5, 6] where 0 is Monday
            return now.weekday() in self.value

        elif self.condition_type == TimeConditionType.DATE_RANGE:
            # Format: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            start_date = datetime.datetime.strptime(
                self.value["start"], "%Y-%m-%d"
            ).date()
            end_date = datetime.datetime.strptime(self.value["end"], "%Y-%m-%d").date()
            current_date = now.date()
            return start_date <= current_date <= end_date

        elif self.condition_type == TimeConditionType.FREQUENCY:
            # Handled by RuleEngine directly
            return True

        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "condition_type": self.condition_type.value,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeCondition":
        """Create from dictionary (for deserialization)."""
        return cls(
            condition_type=data["condition_type"],
            value=data["value"],
        )


class RuleAction:
    """Represents an action to take when a rule is matched."""

    def __init__(
        self,
        action_type: str | ActionType,
        parameters: dict[str, Any],
    ) -> None:
        """
        Initialize a rule action.

        Args:
            action_type: The type of action
            parameters: Parameters for the action
        """
        self.action_type = (
            action_type
            if isinstance(action_type, ActionType)
            else ActionType(action_type)
        )
        self.parameters = parameters

    async def apply(
        self, notification: Notification, context: dict[str, Any]
    ) -> Notification:
        """
        Apply the action to a notification.

        Args:
            notification: The notification to modify
            context: Additional context for the action

        Returns:
            The modified notification
        """
        if self.action_type == ActionType.ROUTE:
            # Routing is handled by the rule engine
            return notification

        elif self.action_type == ActionType.TRANSFORM:
            # Apply transformations to the notification
            if "level" in self.parameters:
                notification.level = NotificationLevel.from_string(
                    self.parameters["level"]
                )

            if "type" in self.parameters:
                try:
                    notification.notification_type = NotificationType(
                        self.parameters["type"]
                    )
                except ValueError:
                    pass

            if "message" in self.parameters:
                message_template = self.parameters["message"]
                try:
                    # Replace placeholders with values from the notification
                    notification.message = message_template.format(
                        level=notification.level.name,
                        type=notification.notification_type.value,
                        source=notification.source,
                        message=notification.message,
                        **notification.details,
                    )
                except (KeyError, ValueError):
                    # If formatting fails, keep the original message
                    pass

            if "source" in self.parameters:
                notification.source = self.parameters["source"]

            return notification

        elif self.action_type == ActionType.ENRICH:
            # Add additional data to the notification
            if "add_fields" in self.parameters:
                for key, value in self.parameters["add_fields"].items():
                    if key not in notification.details:
                        notification.details[key] = value

            if "add_context" in self.parameters and context:
                for key in self.parameters["add_context"]:
                    if key in context and key not in notification.details:
                        notification.details[key] = context[key]

            return notification

        elif self.action_type == ActionType.BLOCK:
            # Blocking is handled by the rule engine
            return notification

        elif self.action_type == ActionType.THROTTLE:
            # Throttling is handled by the rule engine
            return notification

        return notification

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action_type": self.action_type.value,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuleAction":
        """Create from dictionary (for deserialization)."""
        return cls(
            action_type=data["action_type"],
            parameters=data["parameters"],
        )


class NotificationRule:
    """Represents a rule for processing notifications."""

    def __init__(
        self,
        name: str,
        description: str,
        conditions: list[RuleCondition],
        time_conditions: list[TimeCondition] | None = None,
        actions: list[RuleAction] | None = None,
        enabled: bool = True,
        priority: int = 100,
        subscribers: list[str] | None = None,
        rule_id: str | None = None,
    ) -> None:
        """
        Initialize a notification rule.

        Args:
            name: Name of the rule
            description: Description of what the rule does
            conditions: List of conditions that must be met
            time_conditions: Optional time-based conditions
            actions: Actions to take when the rule matches
            enabled: Whether the rule is active
            priority: Rule priority (lower numbers = higher priority)
            subscribers: List of subscribers to route to (None = all)
            rule_id: Unique identifier for the rule
        """
        self.name = name
        self.description = description
        self.conditions = conditions or []
        self.time_conditions = time_conditions or []
        self.actions = actions or []
        self.enabled = enabled
        self.priority = priority
        self.subscribers = subscribers  # None means all subscribers
        self.rule_id = rule_id or f"rule_{int(datetime.datetime.now().timestamp())}"
        self.match_count = 0
        self.last_match_time: float | None = None

    async def matches(
        self, notification: Notification, context: dict[str, Any] | None = None
    ) -> bool:
        """
        Check if a notification matches this rule.

        Args:
            notification: The notification to check
            context: Additional context for evaluation

        Returns:
            True if the rule matches, False otherwise
        """
        if not self.enabled:
            return False

        # Check all conditions
        for condition in self.conditions:
            if not await condition.evaluate(notification):
                return False

        # Check time conditions
        for time_condition in self.time_conditions:
            if not await time_condition.evaluate():
                return False

        # If we got here, all conditions matched
        self.match_count += 1
        self.last_match_time = datetime.datetime.now().timestamp()
        return True

    async def apply_actions(
        self, notification: Notification, context: dict[str, Any] | None = None
    ) -> Notification:
        """
        Apply all actions to a notification.

        Args:
            notification: The notification to modify
            context: Additional context for actions

        Returns:
            The modified notification
        """
        context = context or {}
        modified_notification = notification

        for action in self.actions:
            modified_notification = await action.apply(modified_notification, context)

        return modified_notification

    def should_block(self) -> bool:
        """Check if this rule blocks the notification."""
        return any(action.action_type == ActionType.BLOCK for action in self.actions)

    def should_throttle(self) -> dict[str, Any] | None:
        """
        Check if this rule applies custom throttling.

        Returns:
            Throttling parameters or None
        """
        for action in self.actions:
            if action.action_type == ActionType.THROTTLE:
                return action.parameters
        return None

    def get_route_subscribers(self) -> list[str] | None:
        """
        Get the subscribers this rule routes to.

        Returns:
            List of subscriber names or None (all subscribers)
        """
        for action in self.actions:
            if action.action_type == ActionType.ROUTE:
                return action.parameters.get("subscribers")
        return self.subscribers

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "conditions": [c.to_dict() for c in self.conditions],
            "time_conditions": [tc.to_dict() for tc in self.time_conditions],
            "actions": [a.to_dict() for a in self.actions],
            "enabled": self.enabled,
            "priority": self.priority,
            "subscribers": self.subscribers,
            "stats": {
                "match_count": self.match_count,
                "last_match_time": self.last_match_time,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NotificationRule":
        """Create from dictionary (for deserialization)."""
        rule = cls(
            name=data["name"],
            description=data["description"],
            conditions=[RuleCondition.from_dict(c) for c in data["conditions"]],
            time_conditions=[
                TimeCondition.from_dict(tc) for tc in data.get("time_conditions", [])
            ],
            actions=[RuleAction.from_dict(a) for a in data.get("actions", [])],
            enabled=data.get("enabled", True),
            priority=data.get("priority", 100),
            subscribers=data.get("subscribers"),
            rule_id=data["rule_id"],
        )

        # Restore statistics if available
        if "stats" in data:
            rule.match_count = data["stats"].get("match_count", 0)
            rule.last_match_time = data["stats"].get("last_match_time")

        return rule


class RuleEngine:
    """
    Engine for evaluating notification rules.

    The rule engine provides:
    - Rule storage and retrieval
    - Rule evaluation against notifications
    - Custom notification routing based on rules
    - Statistics about rule matches
    """

    def __init__(self) -> None:
        """Initialize the rule engine."""
        self.rules: list[NotificationRule] = []
        self.initialized = False
        self.frequency_cache: dict[str, list[float]] = {}

    async def initialize(self) -> None:
        """Load rules from storage."""
        if self.initialized:
            return

        # Create rule storage if it doesn't exist
        if not RULES_DB_PATH.exists():
            await AsyncFileIO.write_json(RULES_DB_PATH, {"rules": []})

        # Load rules
        try:
            data = await AsyncFileIO.read_json(RULES_DB_PATH)
            self.rules = [
                NotificationRule.from_dict(rule_data)
                for rule_data in data.get("rules", [])
            ]
            self.rules.sort(key=lambda r: r.priority)
        except Exception as e:
            logger.error(f"Error loading notification rules: {e}")
            self.rules = []

        self.initialized = True
        logger.info(f"Loaded {len(self.rules)} notification rules")

    async def save_rules(self) -> None:
        """Save rules to storage."""
        try:
            data = {"rules": [rule.to_dict() for rule in self.rules]}
            await AsyncFileIO.write_json(RULES_DB_PATH, data)
        except Exception as e:
            logger.error(f"Error saving notification rules: {e}")

    async def add_rule(self, rule: NotificationRule) -> str:
        """
        Add a new rule to the engine.

        Args:
            rule: The rule to add

        Returns:
            The rule ID
        """
        await self.initialize()
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)
        await self.save_rules()
        return rule.rule_id

    async def update_rule(self, rule: NotificationRule) -> bool:
        """
        Update an existing rule.

        Args:
            rule: The updated rule

        Returns:
            True if the rule was updated, False if not found
        """
        await self.initialize()
        for i, existing_rule in enumerate(self.rules):
            if existing_rule.rule_id == rule.rule_id:
                self.rules[i] = rule
                self.rules.sort(key=lambda r: r.priority)
                await self.save_rules()
                return True
        return False

    async def delete_rule(self, rule_id: str) -> bool:
        """
        Delete a rule.

        Args:
            rule_id: The ID of the rule to delete

        Returns:
            True if the rule was deleted, False if not found
        """
        await self.initialize()
        initial_count = len(self.rules)
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        if len(self.rules) < initial_count:
            await self.save_rules()
            return True
        return False

    async def get_rule(self, rule_id: str) -> NotificationRule | None:
        """
        Get a rule by ID.

        Args:
            rule_id: The rule ID

        Returns:
            The rule or None if not found
        """
        await self.initialize()
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    async def get_all_rules(self) -> list[dict[str, Any]]:
        """
        Get all rules.

        Returns:
            List of rule dictionaries
        """
        await self.initialize()
        return [rule.to_dict() for rule in self.rules]

    async def process_notification(
        self, notification: Notification, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Process a notification through the rule engine.

        Args:
            notification: The notification to process
            context: Additional context for rule evaluation

        Returns:
            Dictionary with processing results:
            {
                "blocked": bool,  # Whether the notification was blocked
                "modified": bool,  # Whether the notification was modified
                "notification": Notification,  # The (possibly) modified notification
                "subscribers": list[str] | None,  # Subscribers to route to (None = all)
                "throttle_params": dict | None,  # Custom throttling parameters
                "matched_rules": list[str]  # IDs of rules that matched
            }
        """
        await self.initialize()
        context = context or {}
        modified_notification = notification
        result = {
            "blocked": False,
            "modified": False,
            "notification": notification,
            "subscribers": None,  # None means all subscribers
            "throttle_params": None,
            "matched_rules": [],
        }

        # Check frequency-based time conditions
        await self._update_frequency_cache(notification)

        # Process rules in priority order
        for rule in self.rules:
            # Add frequency cache to context
            context["frequency_cache"] = self.frequency_cache

            # Check if rule matches
            if await rule.matches(modified_notification, context):
                result["matched_rules"].append(rule.rule_id)

                # Check if rule blocks the notification
                if rule.should_block():
                    result["blocked"] = True
                    break

                # Apply rule actions
                new_notification = await rule.apply_actions(
                    modified_notification, context
                )
                if new_notification is not modified_notification:
                    modified_notification = new_notification
                    result["modified"] = True

                # Check for throttling
                throttle_params = rule.should_throttle()
                if throttle_params:
                    result["throttle_params"] = throttle_params

                # Check for routing
                subscribers = rule.get_route_subscribers()
                if subscribers is not None:
                    result["subscribers"] = subscribers

        result["notification"] = modified_notification
        return result

    async def _update_frequency_cache(self, notification: Notification) -> None:
        """
        Update the frequency cache for a notification.

        This is used for frequency-based time conditions.

        Args:
            notification: The notification to add to the cache
        """
        # Create cache keys based on notification properties
        cache_keys = [
            f"level:{notification.level.name}",
            f"type:{notification.notification_type.value}",
            f"source:{notification.source}"
            if notification.source
            else "source:unknown",
        ]

        # Add keys for specific combinations
        cache_keys.append(
            f"level:{notification.level.name}:type:{notification.notification_type.value}"
        )

        # Add the current timestamp to each relevant cache entry
        now = datetime.datetime.now().timestamp()
        for key in cache_keys:
            if key not in self.frequency_cache:
                self.frequency_cache[key] = []
            self.frequency_cache[key].append(now)

            # Clean up old entries (older than 1 hour)
            one_hour_ago = now - 3600
            self.frequency_cache[key] = [
                ts for ts in self.frequency_cache[key] if ts > one_hour_ago
            ]

    async def simulate_rule(
        self, rule: NotificationRule, notification: Notification
    ) -> dict[str, Any]:
        """
        Simulate a rule against a notification without side effects.

        Args:
            rule: The rule to simulate
            notification: The notification to test

        Returns:
            Simulation results
        """
        matches = await rule.matches(notification)
        modified_notification = None
        if matches:
            modified_notification = await rule.apply_actions(notification, {})

        return {
            "rule": rule.to_dict(),
            "matches": matches,
            "notification_before": notification.to_dict(),
            "notification_after": (
                modified_notification.to_dict() if modified_notification else None
            ),
            "would_block": rule.should_block() if matches else False,
            "would_route_to": rule.get_route_subscribers() if matches else None,
            "would_throttle": rule.should_throttle() if matches else None,
        }


# Create a singleton instance
rule_engine = RuleEngine()
