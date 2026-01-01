from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncio

    import aiomqtt as mqtt
    from fastapi import WebSocket
    from private_assistant_commons import MqttConfig, messages

    from app.utils import config

logger = logging.getLogger(__name__)


class SupportUtils:
    def __init__(self) -> None:
        self._config_obj: config.Config | None = None
        self._mqtt_config: MqttConfig | None = None
        self._mqtt_client: mqtt.Client | None = None
        self.mqtt_subscription_to_queue: dict[str, asyncio.Queue[messages.Response]] = {}
        self.active_connections: dict[int, WebSocket] = {}
        self.mqtt_connected: bool = False

    @property
    def config_obj(self) -> config.Config:
        if self._config_obj is None:
            raise ValueError("Config object is not set")
        return self._config_obj

    @config_obj.setter
    def config_obj(self, value: config.Config) -> None:
        self._config_obj = value

    @property
    def mqtt_config(self) -> MqttConfig:
        if self._mqtt_config is None:
            raise ValueError("MQTT config is not set")
        return self._mqtt_config

    @mqtt_config.setter
    def mqtt_config(self, value: MqttConfig) -> None:
        self._mqtt_config = value

    @property
    def mqtt_client(self) -> mqtt.Client:
        if self._mqtt_client is None:
            raise ValueError("MQTT client is not set")
        return self._mqtt_client

    @mqtt_client.setter
    def mqtt_client(self, value: mqtt.Client) -> None:
        self._mqtt_client = value
