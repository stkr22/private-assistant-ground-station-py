from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

    import aiomqtt as mqtt
    from fastapi import WebSocket
    from private_assistant_commons import messages

    from app.utils import config

logger = logging.getLogger(__name__)


class SupportUtils:
    def __init__(self) -> None:
        self._config_obj: config.Config | None = None
        self._mqtt_client: mqtt.Client | None = None
        self.mqtt_subscription_to_queue: dict[str, asyncio.Queue[messages.Response]] = {}
        self.active_connections: dict[int, WebSocket] = {}
        self.mqtt_connected: bool = False
        self.mqtt_subscriptions: set[str] = set()

    @property
    def config_obj(self) -> config.Config:
        if self._config_obj is None:
            raise ValueError("Config object is not set")
        return self._config_obj

    @config_obj.setter
    def config_obj(self, value: config.Config) -> None:
        self._config_obj = value

    @property
    def mqtt_client(self) -> mqtt.Client:
        if self._mqtt_client is None:
            raise ValueError("MQTT client is not set")
        return self._mqtt_client

    @mqtt_client.setter
    def mqtt_client(self, value: mqtt.Client) -> None:
        self._mqtt_client = value

    def is_mqtt_connected(self) -> bool:
        """Check if MQTT client is currently connected."""
        return self.mqtt_connected and self._mqtt_client is not None

    async def safe_publish(self, topic: str, payload: str | bytes | None, qos: int = 0) -> bool:
        """
        Safely publish to MQTT, handling disconnection gracefully.

        Args:
            topic: MQTT topic to publish to
            payload: Message payload
            qos: Quality of Service level

        Returns:
            True if published successfully, False if disconnected or failed
        """
        if not self.is_mqtt_connected():
            logger.warning("Cannot publish to MQTT: not connected. Topic: %s", topic)
            return False

        try:
            await self.mqtt_client.publish(topic, payload, qos=qos)
            return True
        except Exception as e:
            logger.error("Failed to publish to MQTT topic %s: %s", topic, e)
            return False
