"""Tests for configuration module."""

import tempfile
from pathlib import Path

import pytest
import yaml

from app.utils.config import Config, load_config


class TestConfig:
    """Test configuration loading and validation."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = Config()
        
        assert config.speech_transcription_api == "http://localhost:8000/transcribe"
        assert config.speech_synthesis_api == "http://localhost:8080/synthesizeSpeech"
        assert config.max_command_input_seconds == 30  # noqa: PLR2004
        assert config.mqtt_server_host == "localhost"
        assert config.mqtt_server_port == 1883  # noqa: PLR2004
        assert config.broadcast_topic == "assistant/ground_station/broadcast"

    def test_config_topics(self):
        """Test topic generation."""
        config = Config(client_id="test-station")
        
        assert config.base_topic == "assistant/ground_station/all/test-station"
        assert config.input_topic == "assistant/ground_station/all/test-station/input"
        assert config.output_topic == "assistant/ground_station/all/test-station/output"

    def test_config_topic_overrides(self):
        """Test topic overrides."""
        config = Config(
            base_topic_overwrite="custom/base",
            input_topic_overwrite="custom/input",
            output_topic_overwrite="custom/output"
        )
        
        assert config.base_topic == "custom/base"
        assert config.input_topic == "custom/input"
        assert config.output_topic == "custom/output"

    def test_load_config_from_yaml(self):
        """Test loading configuration from YAML file."""
        config_data = {
            "speech_transcription_api": "http://test:8000/stt",
            "speech_synthesis_api": "http://test:8080/tts",
            "mqtt_server_host": "test-mqtt",
            "mqtt_server_port": 1234,
            "max_command_input_seconds": 60
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump(config_data, f)
            config_path = Path(f.name)
        
        try:
            config = load_config(config_path)
            
            assert config.speech_transcription_api == "http://test:8000/stt"
            assert config.speech_synthesis_api == "http://test:8080/tts"
            assert config.mqtt_server_host == "test-mqtt"
            assert config.mqtt_server_port == 1234  # noqa: PLR2004
            assert config.max_command_input_seconds == 60  # noqa: PLR2004
        finally:
            config_path.unlink()

    def test_load_config_file_not_found(self):
        """Test error handling for missing config file."""
        with pytest.raises(FileNotFoundError):
            load_config(Path("nonexistent.yaml"))

    def test_config_with_auth_tokens(self):
        """Test configuration with authentication tokens."""
        config = Config(
            speech_transcription_api_token="stt-token-123",
            speech_synthesis_api_token="tts-token-456"
        )
        
        assert config.speech_transcription_api_token == "stt-token-123"
        assert config.speech_synthesis_api_token == "tts-token-456"