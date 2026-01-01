"""Tests for configuration module."""

import tempfile
from pathlib import Path

import pytest
import yaml
from private_assistant_commons import MqttConfig

from app.utils.config import Config, load_config


class TestConfig:
    """Test configuration loading and validation."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = Config()

        assert config.speech_transcription_api == "http://localhost:8000/transcribe"
        assert config.speech_synthesis_api == "http://localhost:8080/synthesizeSpeech"
        assert config.max_command_input_seconds == 30  # noqa: PLR2004
        # broadcast_topic inherited from CommonsSkillConfig
        assert config.broadcast_topic == "assistant/broadcast"
        # MQTT config is loaded separately, not part of Config

    def test_config_topics(self):
        """Test topic generation."""
        config = Config(client_id="test-station")

        assert config.client_topic == "assistant/ground_station/all/test-station"
        assert config.input_topic == "assistant/ground_station/all/test-station/input"
        assert config.output_topic == "assistant/ground_station/all/test-station/output"

    def test_config_topic_overrides(self):
        """Test topic overrides."""
        config = Config(
            client_topic_overwrite="custom/client",
            input_topic_overwrite="custom/input",
            output_topic_overwrite="custom/output",
        )

        assert config.client_topic == "custom/client"
        assert config.input_topic == "custom/input"
        assert config.output_topic == "custom/output"

    def test_load_config_from_yaml(self):
        """Test loading configuration from YAML file."""
        config_data = {
            "speech_transcription_api": "http://test:8000/stt",
            "speech_synthesis_api": "http://test:8080/tts",
            "max_command_input_seconds": 60,
            "client_id": "test-station",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)

            assert config.speech_transcription_api == "http://test:8000/stt"
            assert config.speech_synthesis_api == "http://test:8080/tts"
            assert config.max_command_input_seconds == 60  # noqa: PLR2004
            assert config.client_id == "test-station"
        finally:
            config_path.unlink()

    def test_load_config_file_not_found(self):
        """Test error handling for missing config file."""
        with pytest.raises(FileNotFoundError):
            load_config(Path("nonexistent.yaml"))

    def test_config_with_auth_tokens(self):
        """Test configuration with authentication tokens."""
        config = Config(speech_transcription_api_token="stt-token-123", speech_synthesis_api_token="tts-token-456")

        assert config.speech_transcription_api_token == "stt-token-123"
        assert config.speech_synthesis_api_token == "tts-token-456"


class TestMqttConfig:
    """Test MQTT configuration loaded separately from commons."""

    def test_mqtt_config_with_defaults(self):
        """Test MqttConfig with provided defaults."""
        mqtt_config = MqttConfig(host="localhost", port=1883)

        assert mqtt_config.host == "localhost"
        assert mqtt_config.port == 1883  # noqa: PLR2004
        assert mqtt_config.username is None
        assert mqtt_config.password is None

    def test_mqtt_config_with_auth(self):
        """Test MqttConfig with authentication."""
        mqtt_config = MqttConfig(host="secure-broker", port=8883, username="test-user", password="test-pass")

        assert mqtt_config.host == "secure-broker"
        assert mqtt_config.port == 8883  # noqa: PLR2004
        assert mqtt_config.username == "test-user"
        assert mqtt_config.password == "test-pass"

    def test_mqtt_config_minimal(self):
        """Test MqttConfig with minimal required fields."""
        mqtt_config = MqttConfig(host="mqtt.example.com", port=1883)

        assert mqtt_config.host == "mqtt.example.com"
        assert mqtt_config.port == 1883  # noqa: PLR2004
