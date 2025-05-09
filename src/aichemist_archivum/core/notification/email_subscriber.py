"""Email subscriber for the notification system."""

import asyncio
import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate
from typing import Any

from the_aichemist_codex.infrastructure.notification.notification_manager import (
    Notification,
    NotificationSubscriber,
)

logger = logging.getLogger(__name__)


class EmailSubscriber(NotificationSubscriber):
    """Subscriber that sends notifications via email."""

    def __init__(self, name: str, settings: dict[str, Any] | None = None) -> None:
        """
        Initialize the email subscriber.

        Args:
            name: Name of the subscriber
            settings: Subscriber-specific settings including:
                - smtp_server: SMTP server address
                - smtp_port: SMTP server port
                - use_tls: Whether to use TLS encryption
                - username: SMTP username for authentication
                - password: SMTP password for authentication
                - from_address: Sender email address
                - to_addresses: List of recipient email addresses
                - subject_prefix: Prefix for email subjects
                - batch_mode: Whether to send emails in batches
                - batch_interval: Seconds between batch sends
                - max_batch_size: Maximum number of notifications in a batch
        """
        super().__init__(name, settings)

        # Extract email-specific settings
        self.smtp_server = self.settings.get("smtp_server", "localhost")
        self.smtp_port = self.settings.get("smtp_port", 25)
        self.use_tls = self.settings.get("use_tls", False)
        self.username = self.settings.get("username")
        self.password = self.settings.get("password")
        self.from_address = self.settings.get("from_address", "codex@example.com")
        self.to_addresses = self.settings.get("to_addresses", [])
        self.subject_prefix = self.settings.get("subject_prefix", "[AIchemist Codex] ")

        # Batch mode settings
        self.batch_mode = self.settings.get("batch_mode", False)
        self.batch_interval = self.settings.get("batch_interval", 300)  # 5 minutes
        self.max_batch_size = self.settings.get("max_batch_size", 20)

        # Initialize batch queue if in batch mode
        self.batch_queue: list[Notification] = []
        self._batch_task = None

        # Validate required settings
        if not self.to_addresses:
            logger.warning("EmailSubscriber initialized with no recipient addresses")
            self.enabled = False

        # Start batch sending task if enabled
        if self.enabled and self.batch_mode:
            self._start_batch_task()

    def _start_batch_task(self) -> None:
        """Start the background task for batch email sending."""
        if self._batch_task is None:
            self._batch_task = asyncio.create_task(self._batch_send_loop())
            logger.debug("Started email batch sending task")

    async def _batch_send_loop(self) -> None:
        """Background task that sends batched emails periodically."""
        try:
            while True:
                await asyncio.sleep(self.batch_interval)

                # Check if we have any notifications to send
                if self.batch_queue:
                    notifications = self.batch_queue.copy()
                    self.batch_queue = []

                    # Send the batch
                    await self._send_batch_email(notifications)
        except asyncio.CancelledError:
            logger.debug("Email batch sending task cancelled")
        except Exception as e:
            logger.error(f"Error in email batch sending task: {e}")

    async def _process_notification(self, notification: Notification) -> bool:
        """
        Process notification by sending an email or adding to batch.

        Args:
            notification: The notification to process

        Returns:
            True if notification was processed successfully
        """
        # If in batch mode, add to queue and return
        if self.batch_mode:
            self.batch_queue.append(notification)

            # If queue is getting too large, send immediately
            if len(self.batch_queue) >= self.max_batch_size:
                notifications = self.batch_queue.copy()
                self.batch_queue = []
                return await self._send_batch_email(notifications)

            return True

        # Otherwise, send immediately
        return await self._send_single_email(notification)

    async def _send_single_email(self, notification: Notification) -> bool:
        """
        Send a single notification as an email.

        Args:
            notification: The notification to send

        Returns:
            True if the email was sent successfully
        """
        # Create email message
        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = ", ".join(self.to_addresses)
        msg["Date"] = formatdate(localtime=True)

        # Create subject based on notification level and type
        subject = (
            f"{self.subject_prefix}{notification.level.name}: "
            f"{notification.notification_type.name.capitalize()}"
        )
        if notification.source:
            subject = f"{subject} - {notification.source}"
        msg["Subject"] = subject

        # Create email body
        body = [f"Message: {notification.message}"]

        # Add timestamp
        timestamp = datetime.fromtimestamp(notification.timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        body.append(f"\nTimestamp: {timestamp}")

        # Add details if present
        if notification.details:
            body.append("\nDetails:")
            for key, value in notification.details.items():
                body.append(f"  {key}: {value}")

        # Set message content
        msg.set_content("\n".join(body))

        # Send the email
        return await self._send_email_message(msg)

    async def _send_batch_email(self, notifications: list[Notification]) -> bool:
        """
        Send multiple notifications in a single email.

        Args:
            notifications: List of notifications to send

        Returns:
            True if the email was sent successfully
        """
        if not notifications:
            return True

        # Create email message
        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = ", ".join(self.to_addresses)
        msg["Date"] = formatdate(localtime=True)

        # Create subject based on batch size and highest level
        highest_level = max(n.level for n in notifications)
        count = len(notifications)
        msg["Subject"] = (
            f"{self.subject_prefix}{highest_level.name}: {count} New Notifications"
        )

        # Create email body
        body = [f"The Aichemist Codex has {count} new notifications:"]
        body.append("")

        # Group notifications by type
        grouped: dict[str, list[Notification]] = {}
        for notification in notifications:
            notification_type = notification.notification_type.name
            if notification_type not in grouped:
                grouped[notification_type] = []
            grouped[notification_type].append(notification)

        # Add each group to the email
        for notification_type, group in grouped.items():
            body.append(
                f"## {notification_type.capitalize()} Notifications ({len(group)}):"
            )
            body.append("")

            for i, notification in enumerate(
                sorted(group, key=lambda n: n.level.value, reverse=True), 1
            ):
                timestamp = datetime.fromtimestamp(notification.timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                body.append(f"{i}. [{notification.level.name}] {notification.message}")
                body.append(f"   Time: {timestamp}")
                if notification.source:
                    body.append(f"   Source: {notification.source}")
                if notification.details:
                    body.append(f"   Details: {notification.details}")
                body.append("")

        # Set message content
        msg.set_content("\n".join(body))

        # Send the email
        return await self._send_email_message(msg)

    async def _send_email_message(self, msg: EmailMessage) -> bool:
        """
        Send an email message via SMTP.

        Args:
            msg: The email message to send

        Returns:
            True if the email was sent successfully
        """
        # Run SMTP sending in a thread pool to avoid blocking
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._send_email_sync, msg)
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _send_email_sync(self, msg: EmailMessage) -> bool:
        """
        Synchronous implementation of email sending.

        Args:
            msg: The email message to send

        Returns:
            True if the email was sent successfully
        """
        try:
            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                # Use TLS if configured
                if self.use_tls:
                    server.starttls()

                # Login if credentials are provided
                if self.username and self.password:
                    server.login(self.username, self.password)

                # Send the email
                server.send_message(msg)

            logger.debug(f"Email sent to {msg['To']}")
            return True
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False
