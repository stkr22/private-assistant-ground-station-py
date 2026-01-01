import logging
import socket
from pathlib import Path

import yaml
from private_assistant_commons import SkillConfig as CommonsSkillConfig
from pydantic import Field, ValidationError

logger = logging.getLogger(__name__)


class Config(CommonsSkillConfig):
    """Ground station configuration extending commons SkillConfig.

    Inherits from CommonsSkillConfig:
    - broadcast_topic: str = "assistant/broadcast"
    - base_topic: str = "assistant"
    - client_id: str (overridden to use hostname)
    - intent_analysis_result_topic: str = "assistant/intent_engine/result"
    - device_update_topic: str = "assistant/global_device_update"
    - intent_cache_size: int = 1000

    Note: MQTT configuration is loaded separately via commons.MqttConfig
    from MQTT_* environment variables.

    The ground station uses its own client_topic property for organizing
    input/output topics specific to this ground station instance.
    """

    # Speech API configuration
    speech_transcription_api: str = "http://localhost:8000/transcribe"
    speech_transcription_api_token: str | None = None
    speech_synthesis_api: str = "http://localhost:8080/synthesizeSpeech"
    speech_synthesis_api_token: str | None = None

    # Override client_id to use hostname (ground station specific)
    client_id: str = Field(default_factory=socket.gethostname)

    # Ground station specific
    max_command_input_seconds: int = 30
    remote_broadcast_topic: str = "assistant/remote_broadcast"
    client_topic_overwrite: str | None = None
    input_topic_overwrite: str | None = None
    output_topic_overwrite: str | None = None
    text_endpoint_auth_token: str = "DEBUG"

    @property
    def client_topic(self) -> str:
        """Computed client topic for ground station.

        Returns the ground station's specific client topic, which is used
        for input/output topics. Defaults to assistant/ground_station/all/{client_id}.
        """
        return self.client_topic_overwrite or f"assistant/ground_station/all/{self.client_id}"

    @property
    def input_topic(self) -> str:
        """Computed input topic."""
        return self.input_topic_overwrite or f"{self.client_topic}/input"

    @property
    def output_topic(self) -> str:
        """Computed output topic."""
        return self.output_topic_overwrite or f"{self.client_topic}/output"


def load_config(config_path: Path) -> Config:
    try:
        with config_path.open("r") as file:
            config_data = yaml.safe_load(file)
        return Config.model_validate(config_data)
    except FileNotFoundError as err:
        logger.error("Config file not found: %s", config_path)
        raise err
    except ValidationError as err_v:
        logger.error("Validation error: %s", err_v)
        raise err_v
