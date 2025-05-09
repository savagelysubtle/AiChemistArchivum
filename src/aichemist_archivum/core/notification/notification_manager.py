"""
Notification system for managing and delivering notifications.

This module provides a comprehensive notification system with a publisher-subscriber
pattern. It handles creation, storage, and delivery of notifications
across the application. Notifications are categorized by levels (info, warning, error)
and types (system, file, task).

The module uses a centralized data directory to store notifications in JSON format.

Typical usage:
    manager = NotificationManager()
    notification = manager.create_notification(
        "File Processed",
        "File example.txt has been processed successfully",
        NotificationLevel.INFO,
        NotificationType.FILE
    )

    # Subscribe to notifications
    def handle_notification(notification):
        print(f"Received: {notification.title}")
"""

import asyncio
import hashlib
import json
import logging
import time
from enum import Enum, auto
from typing import Any, Generic, TypeVar

from the_aichemist_codex.infrastructure.config.settings import determine_project_root
from the_aichemist_codex.infrastructure.utils.io.async_io import AsyncFileIO

logger = logging.getLogger(__name__)

# Define constants that were previously imported
DATA_DIR = determine_project_root() / "data"
NOTIFICATION_SETTINGS = {
    "max_notifications": 1000,
    "retention_days": 30,
    "throttle_identical": True,
    "throttle_window": 60,  # seconds
}

# Define notification database path
NOTIFICATION_DB_PATH = DATA_DIR / "notifications.json"

# Ensure notification directory exists
(DATA_DIR / "notifications").mkdir(exist_ok=True, parents=True)

# Define a type variable for SimpleCache
T = TypeVar("T")


class NotificationLevel(Enum):
    """
    Enumeration for notification priority levels.

    Attributes:
        INFO: Low priority informational notifications
        WARNING: Medium priority warning notifications
        ERROR: High priority error notifications
        CRITICAL: Highest priority critical notifications
    """

    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

    @classmethod
    def from_string(cls, level_str: str) -> "NotificationLevel":
        """Convert a string level to an enum value."""
        try:
            # Handle case where an int might be passed
            if isinstance(level_str, int):
                # Try to match by value
                for level in cls:
                    if level.value == level_str:
                        return level
                # Fall back to INFO if no match
                return cls.INFO

            return cls[level_str.upper()]
        except KeyError:
            logger.warning(f"Invalid notification level: {level_str}, using INFO")
            return cls.INFO

    def __ge__(self, other: "NotificationLevel") -> bool:
        """Compare notification levels for greater than or equal."""
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __lt__(self, other: "NotificationLevel") -> bool:
        """Compare notification levels for less than."""
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


class NotificationType(Enum):
    """
    Enumeration for notification categories.

    Attributes:
        SYSTEM: System-level notifications related to application functionality
        FILE: File-related notifications for file operations and status
        TASK: Task-related notifications for background job status
        SECURITY: Security-related notifications for access and permissions
        USER: User-related notifications for account and profile updates
    """

    SYSTEM = auto()
    FILE = auto()
    TASK = auto()
    SECURITY = auto()
    USER = auto()


class Notification:
    """
    Represents a single notification with metadata.

    This class encapsulates all notification data including title, message,
    level, type, timestamp, and read status.

    Attributes:
        id: Unique identifier for the notification
        title: Short notification title
        message: Detailed notification message
        level: Priority level (INFO, WARNING, ERROR, CRITICAL)
        type: Category type (SYSTEM, FILE, TASK, etc.)
        timestamp: Creation time of the notification
        read: Whether the notification has been marked as read
        metadata: Additional contextual information for the notification
    """

    def __init__(
        self,
        message: str,
        level: str | NotificationLevel = NotificationLevel.INFO,
        notification_type: str | NotificationType = NotificationType.SYSTEM,
        source: str = "",
        timestamp: float | None = None,
        details: dict[str, Any] | None = None,
        notification_id: str | None = None,
    ) -> None:
        """
        Initialize a notification.

        Args:
            message: The notification message
            level: Severity level
            notification_type: Category of notification
            source: Source of the notification (e.g., component name)
            timestamp: When the notification was created (defaults to now)
            details: Additional structured data
            notification_id: Unique identifier (generated if not provided)
        """
        self.message = message

        # Convert string level to enum if needed
        if isinstance(level, str):
            self.level = NotificationLevel.from_string(level)
        else:
            self.level = level

        # Convert string type to enum if needed
        if isinstance(notification_type, str):
            try:
                self.notification_type = NotificationType(notification_type)
            except ValueError:
                logger.warning(
                    f"Invalid notification type: {notification_type}, using SYSTEM"
                )
                self.notification_type = NotificationType.SYSTEM
        else:
            self.notification_type = notification_type

        self.source = source
        self.timestamp = timestamp or time.time()
        self.details = details or {}

        # Generate ID based on content if not provided
        if notification_id is None:
            content_hash = hashlib.sha256(
                f"{self.message}{self.level.name}{self.notification_type.value}{self.source}{self.timestamp}".encode()
            ).hexdigest()
            self.id = f"{int(self.timestamp)}_{content_hash[:8]}"
        else:
            self.id = notification_id

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "message": self.message,
            "level": self.level.name,
            "type": self.notification_type.value,
            "source": self.source,
            "timestamp": self.timestamp,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Notification":
        """Create from dictionary (for deserialization)."""
        return cls(
            message=data["message"],
            level=data["level"],
            notification_type=data["type"],
            source=data.get("source", ""),
            timestamp=data["timestamp"],
            details=data.get("details", {}),
            notification_id=data["id"],
        )

    def __str__(self) -> str:
        """Return string representation of notification."""
        return f"[{self.level.name}] {self.message} (from {self.source})"


class NotificationSubscriber:
    """Base class for notification subscribers."""

    def __init__(self, name: str, settings: dict[str, Any] | None = None) -> None:
        """
        Initialize a notification subscriber.

        Args:
            name: Name of the subscriber
            settings: Subscriber-specific settings
        """
        self.name = name
        self.settings = settings or {}  # Convert None to empty dict
        self.min_level = NotificationLevel.from_string(
            self.settings.get("min_level", "INFO")
        )
        self.enabled = self.settings.get("enabled", True)

    async def notify(self, notification: Notification) -> bool:
        """
        Process a notification.

        Args:
            notification: The notification to process

        Returns:
            True if notification was successfully processed
        """
        # Skip if subscriber is disabled or notification level is too low
        if not self.enabled or notification.level < self.min_level:
            return False

        try:
            return await self._process_notification(notification)
        except Exception as e:
            logger.error(f"Error in {self.name} subscriber: {e}")
            return False

    async def _process_notification(self, notification: Notification) -> bool:
        """
        Process a notification (to be implemented by subclasses).

        Args:
            notification: The notification to process

        Returns:
            True if notification was successfully processed
        """
        raise NotImplementedError("Subscribers must implement _process_notification")


class LogSubscriber(NotificationSubscriber):
    """Subscriber that logs notifications to the application log."""

    async def _process_notification(self, notification: Notification) -> bool:
        """Log the notification using the standard logging system."""
        log_level = notification.level.name.lower()
        log_method = getattr(logger, log_level, logger.info)

        # Format a detailed log message
        message = (
            f"{notification.notification_type.name.upper()}: {notification.message}"
        )
        if notification.source:
            message = f"{message} (Source: {notification.source})"

        # Add details as structured logging
        log_method(message, extra=notification.details)
        return True


class DatabaseSubscriber(NotificationSubscriber):
    """Subscriber that stores notifications in a database."""

    def __init__(self, name: str, settings: dict[str, Any] | None = None) -> None:
        """Initialize the database subscriber."""
        super().__init__(name, settings)
        self.db_path = NOTIFICATION_DB_PATH
        self.max_age_days = self.settings.get("max_age_days", 30)
        self.max_per_type = NOTIFICATION_SETTINGS.get(
            "max_notifications_per_type", 1000
        )
        self.notifications = {}
        self.initialized = False

    async def initialize(self) -> None:
        """Load existing notifications from the database."""
        if self.initialized:
            return

        if self.db_path.exists():
            try:
                content = await AsyncFileIO.read_text(self.db_path)
                self.notifications = json.loads(content)
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Error loading notification database: {e}")
                self.notifications = {}

        self.initialized = True

    async def _process_notification(self, notification: Notification) -> bool:
        """Store the notification in the database."""
        # Initialize if needed
        await self.initialize()

        # Get notifications of this type
        notification_type = notification.notification_type.value
        if notification_type not in self.notifications:
            self.notifications[notification_type] = []

        # Add the new notification
        self.notifications[notification_type].append(notification.to_dict())

        # Enforce maximum per type
        if len(self.notifications[notification_type]) > self.max_per_type:
            # Sort by timestamp (newest first) and trim
            self.notifications[notification_type].sort(
                key=lambda n: n["timestamp"], reverse=True
            )
            self.notifications[notification_type] = self.notifications[
                notification_type
            ][: self.max_per_type]

        # Save to disk
        await self._save_notifications()

        return True

    async def _save_notifications(self) -> bool:
        """Save notifications to the database file."""
        try:
            content = json.dumps(self.notifications, indent=2)
            return await AsyncFileIO.write(self.db_path, content)
        except Exception as e:
            logger.error(f"Error saving notifications: {e}")
            return False

    async def cleanup_old_notifications(self) -> int:
        """
        Remove notifications older than max_age_days.

        Returns:
            Number of notifications removed
        """
        await self.initialize()

        removed_count = 0
        cutoff_time = time.time() - (self.max_age_days * 86400)  # 86400 seconds per day

        for notification_type in self.notifications:
            original_count = len(self.notifications[notification_type])
            self.notifications[notification_type] = [
                n
                for n in self.notifications[notification_type]
                if n["timestamp"] >= cutoff_time
            ]
            removed_count += original_count - len(self.notifications[notification_type])

        if removed_count > 0:
            await self._save_notifications()
            logger.info(f"Removed {removed_count} old notifications")

        return removed_count


# Simple in-memory cache implementation for throttling
class SimpleCache(Generic[T]):
    """Simple in-memory cache with TTL."""

    def __init__(self, ttl: int = 60, max_size: int = 1000) -> None:
        """
        Initialize the cache.

        Args:
            ttl: Time-to-live in seconds
            max_size: Maximum number of items in cache
        """
        self.ttl = ttl
        self.max_size = max_size
        self.cache: dict[str, tuple[T, float]] = {}

    def get(self, key: str, default: T = None) -> T:  # type: ignore
        """Get value from cache, returning default if expired or not found."""
        if key not in self.cache:
            return default

        value, expiry = self.cache[key]
        if time.time() > expiry:
            # Expired
            del self.cache[key]
            return default

        return value

    def set(self, key: str, value: T) -> None:
        """Set value in cache with TTL."""
        # Clean up if we're at max size
        if len(self.cache) >= self.max_size and key not in self.cache:
            # Simple cleanup: remove expired items
            now = time.time()
            expired_keys = [k for k, (_, exp) in self.cache.items() if now > exp]
            for k in expired_keys:
                del self.cache[k]

            # If still at max size, remove random item
            if len(self.cache) >= self.max_size:
                if self.cache:
                    del self.cache[next(iter(self.cache))]

        self.cache[key] = (value, time.time() + self.ttl)


class NotificationManager:
    """
    Manages creation, storage, and delivery of notifications.

    This class implements a publisher-subscriber pattern for notifications,
    allowing components to subscribe to notifications and receive updates
    when new notifications are created.

    Features:
    - Asynchronous notification delivery
    - Persistence to JSON storage
    - Configurable retention policies
    - Filtering by type and level
    - Read/unread status tracking

    Attributes:
        _instance: Singleton instance reference
        _subscribers: Set of callback functions subscribed to notifications
        _notifications: Dictionary of stored notifications by ID
        _lock: Asyncio lock for thread safety
        max_notifications: Maximum number of notifications to keep
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args: object, **kwargs: object) -> "NotificationManager":
        """Ensure NotificationManager is a singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the notification manager."""
        if self._initialized:
            return

        # Load settings
        self.settings = NOTIFICATION_SETTINGS
        self.enabled = self.settings.get("enabled", True)

        # Set up throttling
        self.throttling_enabled = self.settings.get("throttling", {}).get(
            "enabled", True
        )
        self.throttle_window = self.settings.get("throttling", {}).get(
            "window_seconds", 60
        )
        self.max_similar = self.settings.get("throttling", {}).get("max_similar", 5)

        # Create throttling cache
        self.throttle_cache = SimpleCache[int](ttl=self.throttle_window, max_size=1000)

        # Set up subscribers
        self.subscribers: dict[str, NotificationSubscriber] = {}
        self._initialized = True

        # Initialize built-in subscribers
        self._setup_default_subscribers()

        # Initialize rule engine (imported here to avoid circular imports)
        try:
            from the_aichemist_codex.infrastructure.notification.rule_engine import (
                rule_engine,
            )

            self.rule_engine = rule_engine
            logger.debug("Rule engine initialized")
        except ImportError:
            logger.warning("Rule engine module not available")
            self.rule_engine = None

        logger.info("NotificationManager initialized")

    def _setup_default_subscribers(self) -> None:
        """Set up the default notification subscribers."""
        # Add logging subscriber
        log_settings = self.settings.get("channels", {}).get("log", {"enabled": True})
        if log_settings.get("enabled", True):
            self.add_subscriber("log", LogSubscriber("log", log_settings))

        # Add database subscriber
        db_settings = self.settings.get("channels", {}).get(
            "database", {"enabled": True}
        )
        if db_settings.get("enabled", True):
            self.add_subscriber("database", DatabaseSubscriber("database", db_settings))

        # Add email subscriber if enabled
        email_settings = self.settings.get("channels", {}).get(
            "email", {"enabled": False}
        )
        if email_settings.get("enabled", False):
            try:
                # Try to import the EmailSubscriber class
                # Using a more defensive approach to handle potential missing module
                email_module_name = (
                    "the_aichemist_codex.backend.notification.email_subscriber"
                )
                email_class_name = "EmailSubscriber"

                # First check if the module exists
                import importlib.util

                spec = importlib.util.find_spec(email_module_name)
                if spec is not None:
                    email_module = importlib.import_module(email_module_name)
                    if hasattr(email_module, email_class_name):
                        email_subscriber_class = getattr(email_module, email_class_name)
                        self.add_subscriber(
                            "email", email_subscriber_class("email", email_settings)
                        )
                        logger.info("Email notification subscriber registered")
                    else:
                        logger.warning(
                            f"EmailSubscriber class not found in {email_module_name}"
                        )
                else:
                    logger.warning(
                        f"Email subscriber module not found: {email_module_name}"
                    )
            except Exception as e:
                logger.warning(f"Failed to load email subscriber: {e}")

        # Add webhook subscriber if enabled
        webhook_settings = self.settings.get("channels", {}).get(
            "webhook", {"enabled": False}
        )
        if webhook_settings.get("enabled", False):
            try:
                # Try to import the WebhookSubscriber class
                # Using a more defensive approach to handle potential missing module
                webhook_module_name = (
                    "the_aichemist_codex.backend.notification.webhook_subscriber"
                )
                webhook_class_name = "WebhookSubscriber"

                # First check if the module exists
                import importlib.util

                spec = importlib.util.find_spec(webhook_module_name)
                if spec is not None:
                    webhook_module = importlib.import_module(webhook_module_name)
                    if hasattr(webhook_module, webhook_class_name):
                        webhook_subscriber_class = getattr(
                            webhook_module, webhook_class_name
                        )
                        self.add_subscriber(
                            "webhook",
                            webhook_subscriber_class("webhook", webhook_settings),
                        )
                        logger.info("Webhook notification subscriber registered")
                    else:
                        logger.warning(
                            f"WebhookSubscriber class not found "
                            f"in {webhook_module_name}"
                        )
                else:
                    logger.warning(
                        f"Webhook subscriber module not found: {webhook_module_name}"
                    )
            except Exception as e:
                logger.warning(f"Failed to load webhook subscriber: {e}")

    def add_subscriber(self, name: str, subscriber: NotificationSubscriber) -> None:
        """
        Register a new notification subscriber.

        Args:
            name: Unique name for the subscriber
            subscriber: The subscriber instance
        """
        self.subscribers[name] = subscriber
        logger.debug(f"Added notification subscriber: {name}")

    def remove_subscriber(self, name: str) -> bool:
        """
        Remove a notification subscriber.

        Args:
            name: Name of the subscriber to remove

        Returns:
            True if the subscriber was removed
        """
        if name in self.subscribers:
            del self.subscribers[name]
            logger.debug(f"Removed notification subscriber: {name}")
            return True
        return False

    async def notify(
        self,
        message: str,
        level: str | NotificationLevel = NotificationLevel.INFO,
        notification_type: str | NotificationType = NotificationType.SYSTEM,
        source: str = "",
        details: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Create and publish a notification to all subscribers.

        Args:
            message: The notification message
            level: Severity level
            notification_type: Category of notification
            source: Source of the notification
            details: Additional structured data

        Returns:
            Notification ID if published, None if throttled or disabled
        """
        if not self.enabled:
            return None

        # Create the notification
        notification = Notification(
            message=message,
            level=level,
            notification_type=notification_type,
            source=source,
            details=details or {},
        )

        # Process through rule engine if available
        subscribers_to_notify = None
        if hasattr(self, "rule_engine") and self.rule_engine is not None:
            try:
                # Create context for rule evaluation
                context = {
                    "manager": self,
                    "timestamp": time.time(),
                }

                # Process notification through rule engine
                result = await self.rule_engine.process_notification(
                    notification, context
                )

                # Check if notification was blocked by rules
                if result["blocked"]:
                    logger.debug(f"Notification blocked by rules: {notification}")
                    return None

                # Use potentially modified notification
                if result["modified"]:
                    notification = result["notification"]

                # Apply custom throttling if specified
                if result["throttle_params"]:
                    # Custom throttling logic could be implemented here
                    pass

                # Check if specific subscribers are targeted
                if result["subscribers"] is not None:
                    subscribers_to_notify = result["subscribers"]

                if result["matched_rules"]:
                    logger.debug(
                        f"Notification matched rules: "
                        f"{', '.join(result['matched_rules'])}"
                    )
            except Exception as e:
                logger.error(f"Error processing notification through rule engine: {e}")

        # Check throttling
        if self.throttling_enabled and await self._should_throttle(notification):
            logger.debug(f"Throttled notification: {notification}")
            return None

        # Publish to all or selected subscribers
        tasks = []
        for name, subscriber in self.subscribers.items():
            # Skip subscribers not in the target list if specified
            if subscribers_to_notify is not None and name not in subscribers_to_notify:
                continue

            tasks.append(subscriber.notify(notification))

        # Wait for all subscribers to process
        if tasks:
            await asyncio.gather(*tasks)

        return notification.id

    async def _should_throttle(self, notification: Notification) -> bool:
        """
        Check if a notification should be throttled based on similarity.

        Args:
            notification: The notification to check

        Returns:
            True if notification should be throttled
        """
        # Create a throttling key based on type, level, and message
        throttle_key = f"{notification.notification_type.name.upper()}:{notification.level.name}:{notification.message}"

        # Get current count for this key
        current_count = self.throttle_cache.get(throttle_key, 0)

        # Increment count
        self.throttle_cache.set(throttle_key, current_count + 1)

        # Throttle if over the limit
        return current_count >= self.max_similar

    async def get_notifications(
        self,
        notification_type: str | NotificationType | None = None,
        level: str | NotificationLevel | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Get notifications from the database.

        Args:
            notification_type: Filter by notification type
            level: Filter by minimum notification level
            start_time: Filter by start time (timestamp)
            end_time: Filter by end time (timestamp)
            limit: Maximum number of notifications to return
            offset: Number of notifications to skip

        Returns:
            List of notification dictionaries
        """
        # Get the database subscriber
        db_subscriber = self.subscribers.get("database")
        if not db_subscriber or not isinstance(db_subscriber, DatabaseSubscriber):
            logger.warning("Database subscriber not available")
            return []

        # Initialize the database
        await db_subscriber.initialize()

        # Convert type and level to correct format
        if isinstance(notification_type, NotificationType):
            notification_type = notification_type.name  # Use name instead of value

        min_level = None
        if level is not None:
            if isinstance(level, str):
                min_level = NotificationLevel.from_string(level)
            else:
                min_level = level

        # Collect matching notifications
        result = []

        # Determine which notification types to include
        types_to_include = (
            [notification_type]
            if notification_type
            else list(db_subscriber.notifications.keys())
        )

        # Process each type
        for ntype in types_to_include:
            if ntype not in db_subscriber.notifications:
                continue

            for notification_dict in db_subscriber.notifications[ntype]:
                # Apply filters
                if (
                    start_time is not None
                    and notification_dict["timestamp"] < start_time
                ):
                    continue
                if end_time is not None and notification_dict["timestamp"] > end_time:
                    continue
                if (
                    min_level is not None
                    and NotificationLevel.from_string(notification_dict["level"])
                    < min_level
                ):
                    continue

                result.append(notification_dict)

        # Sort by timestamp (newest first)
        result.sort(key=lambda n: n["timestamp"], reverse=True)

        # Apply pagination
        return result[offset : offset + limit]

    async def get_notification_by_id(
        self, notification_id: str
    ) -> dict[str, Any] | None:
        """
        Get a specific notification by ID.

        Args:
            notification_id: The ID of the notification to find

        Returns:
            Notification dictionary if found, None otherwise
        """
        # Get the database subscriber
        db_subscriber = self.subscribers.get("database")
        if not db_subscriber or not isinstance(db_subscriber, DatabaseSubscriber):
            logger.warning("Database subscriber not available")
            return None

        # Initialize the database
        await db_subscriber.initialize()

        # Search for the notification
        for notifications in db_subscriber.notifications.values():
            for notification_dict in notifications:
                if notification_dict["id"] == notification_id:
                    return notification_dict

        return None

    async def cleanup(self) -> int:
        """
        Clean up old notifications.

        Returns:
            Number of notifications removed
        """
        db_subscriber = self.subscribers.get("database")
        if not db_subscriber or not isinstance(db_subscriber, DatabaseSubscriber):
            logger.warning("Database subscriber not available for cleanup")
            return 0

        return await db_subscriber.cleanup_old_notifications()


# Create a singleton instance
notification_manager = NotificationManager()
