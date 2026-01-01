"""Pytest configuration and shared fixtures."""

import tempfile
from pathlib import Path

import numpy as np
import pytest
import yaml
from private_assistant_commons import MqttConfig

from app.utils.config import Config


@pytest.fixture
def temp_config_file():
    """Create a temporary configuration file for testing."""
    config_data = {
        "speech_transcription_api": "http://localhost:8000/transcribe",
        "speech_synthesis_api": "http://localhost:8080/synthesizeSpeech",
        "max_command_input_seconds": 30,
        "client_id": "test-ground-station",
        # MQTT fields removed - loaded separately via MqttConfig
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(config_data, f)
        config_path = Path(f.name)

    yield config_path

    # Cleanup
    config_path.unlink()


@pytest.fixture
def test_config():
    """Create a test configuration instance."""
    return Config(
        speech_transcription_api="http://test-stt:8000/transcribe",
        speech_transcription_api_token="test-stt-token",
        speech_synthesis_api="http://test-tts:8080/synthesize",
        speech_synthesis_api_token="test-tts-token",
        max_command_input_seconds=15,
        client_id="test-station",
        # MQTT fields removed - use test_mqtt_config fixture for MQTT settings
    )


@pytest.fixture
def test_mqtt_config():
    """Create a test MQTT configuration instance."""
    return MqttConfig(host="test-mqtt", port=1883)


@pytest.fixture
def sample_audio_data():
    """Create sample audio data for testing."""
    # Generate 1 second of sine wave at 16kHz
    sample_rate = 16000
    duration = 1.0
    frequency = 440.0  # A4 note

    t = np.linspace(0, duration, int(sample_rate * duration), False)
    return np.sin(2 * np.pi * frequency * t).astype(np.float32)


@pytest.fixture
def sample_audio_bytes():
    """Create sample audio bytes for testing."""
    # Generate some int16 audio data
    audio_int16 = np.array([1000, 2000, 3000, 4000, 5000], dtype=np.int16)
    return audio_int16.tobytes()


# Async test markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
