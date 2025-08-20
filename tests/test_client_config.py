"""Tests for client configuration module."""

import pytest
from pydantic import ValidationError

from app.utils.client_config import ClientConfig


class TestClientConfig:
    """Test client configuration validation."""

    def test_valid_client_config(self):
        """Test valid client configuration."""
        config = ClientConfig(
            samplerate=16000,
            input_channels=1,
            output_channels=1,
            chunk_size=1024,
            room="living_room"
        )
        
        assert config.samplerate == 16000
        assert config.input_channels == 1
        assert config.output_channels == 1
        assert config.chunk_size == 1024
        assert config.room == "living_room"
        assert config.output_topic == ""

    def test_client_config_with_output_topic(self):
        """Test client configuration with output topic."""
        config = ClientConfig(
            samplerate=44100,
            input_channels=2,
            output_channels=2,
            chunk_size=512,
            room="bedroom",
            output_topic="assistant/bedroom/output"
        )
        
        assert config.output_topic == "assistant/bedroom/output"

    def test_client_config_validation_errors(self):
        """Test validation errors for invalid configurations."""
        # Missing required fields
        with pytest.raises(ValidationError):
            ClientConfig()
        
        # Invalid samplerate type
        with pytest.raises(ValidationError):
            ClientConfig(
                samplerate="invalid",
                input_channels=1,
                output_channels=1,
                chunk_size=1024,
                room="test"
            )

    def test_client_config_from_dict(self):
        """Test creating client config from dictionary."""
        data = {
            "samplerate": 22050,
            "input_channels": 1,
            "output_channels": 2,
            "chunk_size": 2048,
            "room": "kitchen"
        }
        
        config = ClientConfig.model_validate(data)
        
        assert config.samplerate == 22050
        assert config.room == "kitchen"

    def test_client_config_serialization(self):
        """Test client config serialization."""
        config = ClientConfig(
            samplerate=16000,
            input_channels=1,
            output_channels=1,
            chunk_size=1024,
            room="office"
        )
        
        data = config.model_dump()
        
        assert data["samplerate"] == 16000
        assert data["room"] == "office"
        assert "output_topic" in data