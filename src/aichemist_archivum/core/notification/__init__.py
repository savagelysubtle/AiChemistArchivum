"""Notification system for The Aichemist Codex."""

from the_aichemist_codex.infrastructure.notification.notification_manager import (
    Notification,
    NotificationLevel,
    NotificationManager,
    NotificationType,
    notification_manager,
)

# Import rule engine components if available
try:
    from the_aichemist_codex.infrastructure.notification.rule_engine import (
        ActionType,
        ConditionOperator,
        NotificationRule,
        RuleAction,
        RuleCondition,
        TimeCondition,
        TimeConditionType,
        rule_engine,
    )

    __all__ = [
        "ActionType",
        "ConditionOperator",
        "Notification",
        "NotificationLevel",
        "NotificationManager",
        "NotificationRule",
        "NotificationType",
        "RuleAction",
        "RuleCondition",
        "TimeCondition",
        "TimeConditionType",
        "notification_manager",
        "rule_engine",
    ]
except ImportError:
    # Rule engine not available
    __all__ = [
        "Notification",
        "NotificationLevel",
        "NotificationManager",
        "NotificationType",
        "notification_manager",
    ]
