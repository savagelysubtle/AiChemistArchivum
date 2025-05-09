"""Webhook subscriber for the notification system."""

import asyncio
import json
import logging
from typing import Any

# Try to import aiohttp, but handle case when it's not installed
try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from the_aichemist_codex.infrastructure.notification.notification_manager import (
    Notification,
    NotificationSubscriber,
)

logger = logging.getLogger(__name__)


class WebhookSubscriber(NotificationSubscriber):
    """Subscriber that sends notifications to external webhooks."""

    def __init__(self, name: str, settings: dict[str, Any] | None = None) -> None:
        """
        Initialize the webhook subscriber.

        Args:
            name: Name of the subscriber
            settings: Subscriber-specific settings including:
                - urls: List of webhook URLs
                - headers: Optional HTTP headers to include
                - timeout: Request timeout in seconds
                - retry_count: Number of times to retry on failure
                - retry_delay: Seconds to wait between retries
        """
        super().__init__(name, settings)

        # Check if aiohttp is available
        if not AIOHTTP_AVAILABLE:
            logger.error(
                "aiohttp package is required for WebhookSubscriber but is not installed"
            )
            self.enabled = False
            return

        # Extract webhook-specific settings
        self.urls = self.settings.get("urls", [])
        self.headers = self.settings.get(
            "headers", {"Content-Type": "application/json"}
        )
        self.timeout = self.settings.get("timeout", 10)
        self.retry_count = self.settings.get("retry_count", 2)
        self.retry_delay = self.settings.get("retry_delay", 1)

        # Validate required settings
        if not self.urls:
            logger.warning("WebhookSubscriber initialized with no URLs")
            self.enabled = False

    async def _process_notification(self, notification: Notification) -> bool:
        """
        Send notification to all configured webhooks.

        Args:
            notification: The notification to send

        Returns:
            True if notification was sent to at least one webhook
        """
        if not AIOHTTP_AVAILABLE or not self.urls:
            return False

        # Prepare the payload
        payload = notification.to_dict()

        # Add additional metadata that might be useful for webhook receivers
        payload["webhook_source"] = f"aichemist_codex_{self.name}"

        # Serialize the payload
        try:
            json_payload = json.dumps(payload)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize webhook payload: {e}")
            return False

        # Send to all webhooks
        results = await asyncio.gather(
            *[self._send_to_webhook(url, json_payload) for url in self.urls],
            return_exceptions=True,
        )

        # Check if at least one succeeded
        return any(result is True for result in results)

    async def _send_to_webhook(self, url: str, payload: str) -> bool:
        """
        Send notification to a single webhook with retries.

        Args:
            url: The webhook URL
            payload: JSON payload to send

        Returns:
            True if the notification was sent successfully
        """
        if not AIOHTTP_AVAILABLE:
            return False

        # Try multiple times if configured
        for attempt in range(self.retry_count + 1):
            try:
                # Use timeout to avoid hanging on unresponsive webhooks
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url,
                        data=payload,
                        headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as response:
                        # Check if response was successful
                        if 200 <= response.status < 300:
                            logger.debug(f"Webhook notification sent to {url}")
                            return True
                        else:
                            error_text = await response.text()
                            logger.warning(
                                f"Webhook notification failed with status "
                                f"{response.status}: {error_text}"
                            )
            except TimeoutError:
                logger.warning(
                    f"Webhook request to {url} timed out after {self.timeout}s"
                )
            except aiohttp.ClientError as e:
                logger.warning(f"Webhook request to {url} failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending webhook to {url}: {e}")

            # If this wasn't the last attempt, wait before retrying
            if attempt < self.retry_count:
                await asyncio.sleep(self.retry_delay)

        return False
