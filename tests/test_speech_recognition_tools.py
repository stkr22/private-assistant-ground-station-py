"""Tests for speech recognition tools module."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import numpy as np
import pytest

from app.utils.config import Config
from app.utils.speech_recognition_tools import STTResponse, int2float, send_audio_to_stt_api, send_text_to_tts_api


class TestUtilityFunctions:
    """Test utility functions."""

    def test_int2float_conversion(self):
        """Test int16 to float32 conversion."""
        # Test with known values
        int_data = np.array([0, 16384, 32767, -16384, -32768], dtype=np.int16)
        float_data = int2float(int_data)

        assert float_data.dtype == np.float32
        assert len(float_data) == len(int_data)

        # Test specific conversions
        assert float_data[0] == 0.0  # 0 -> 0.0
        assert abs(float_data[1] - 0.5) < 0.01  # 16384 -> ~0.5  # noqa: PLR2004
        assert abs(float_data[2] - 1.0) < 0.01  # 32767 -> ~1.0  # noqa: PLR2004

    def test_int2float_zero_array(self):
        """Test conversion with all zeros."""
        int_data = np.zeros(100, dtype=np.int16)
        float_data = int2float(int_data)

        assert float_data.dtype == np.float32
        assert np.all(float_data == 0.0)

    def test_int2float_max_values(self):
        """Test conversion with maximum values."""
        int_data = np.array([32767, -32768], dtype=np.int16)
        float_data = int2float(int_data)

        # Should be normalized to approximately ±1.0
        assert abs(float_data[0] - 1.0) < 0.01  # noqa: PLR2004
        assert abs(float_data[1] + 1.0) < 0.01  # noqa: PLR2004


class TestSTTResponse:
    """Test STTResponse model."""

    def test_stt_response_creation(self):
        """Test STTResponse model creation."""
        response = STTResponse(text="hello world", message="success")

        assert response.text == "hello world"
        assert response.message == "success"

    def test_stt_response_validation(self):
        """Test STTResponse validation."""
        # Valid data
        data = {"text": "test transcription", "message": "ok"}
        response = STTResponse.model_validate(data)

        assert response.text == "test transcription"
        assert response.message == "ok"

    def test_stt_response_json_serialization(self):
        """Test JSON serialization of STTResponse."""
        response = STTResponse(text="test", message="success")
        json_data = response.model_dump()

        assert json_data["text"] == "test"
        assert json_data["message"] == "success"


class TestSendAudioToSTTAPI:
    """Test send_audio_to_stt_api function."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config(
            speech_transcription_api="http://test-stt:8000/transcribe", speech_transcription_api_token="test-token-123"
        )

    @pytest.fixture
    def audio_data(self):
        """Create test audio data."""
        return np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_successful_stt_request(self, mock_client_class, config, audio_data):
        """Test successful STT API request."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "hello world", "message": "success"}
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Call function
        result = await send_audio_to_stt_api(audio_data, config)

        # Verify result
        assert result is not None
        assert result.text == "hello world"
        assert result.message == "success"

        # Verify API call
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == config.speech_transcription_api
        assert "file" in call_args[1]["files"]
        assert call_args[1]["headers"]["user-token"] == "test-token-123"

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_stt_timeout_error(self, mock_client_class, config, audio_data):
        """Test STT API timeout error."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await send_audio_to_stt_api(audio_data, config, timeout=1.0)

        assert result is None

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_stt_http_error(self, mock_client_class, config, audio_data):
        """Test STT API HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await send_audio_to_stt_api(audio_data, config)

        assert result is None

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_stt_network_error(self, mock_client_class, config, audio_data):
        """Test STT API network error."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.RequestError("Network error")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await send_audio_to_stt_api(audio_data, config)

        assert result is None

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_stt_no_token(self, mock_client_class, config, audio_data):
        """Test STT API request without token."""
        config.speech_transcription_api_token = None

        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "test", "message": "ok"}
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        await send_audio_to_stt_api(audio_data, config)

        # Verify empty token header
        call_args = mock_client.post.call_args
        assert call_args[1]["headers"]["user-token"] == ""


class TestSendTextToTTSAPI:
    """Test send_text_to_tts_api function."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config(
            speech_synthesis_api="http://test-tts:8080/synthesize", speech_synthesis_api_token="tts-token-456"
        )

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_successful_tts_request(self, mock_client_class, config):
        """Test successful TTS API request."""
        # Setup mock response with audio data
        audio_content = b"fake_audio_data_12345"
        mock_response = MagicMock()
        mock_response.content = audio_content
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Call function
        result = await send_text_to_tts_api("hello world", config, sample_rate=22050)

        # Verify result
        assert result == audio_content

        # Verify API call
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]["url"] == config.speech_synthesis_api
        assert call_args[1]["json"]["text"] == "hello world"
        assert call_args[1]["json"]["sample_rate"] == 22050  # noqa: PLR2004
        assert call_args[1]["headers"]["user-token"] == "tts-token-456"

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_tts_insufficient_audio_data(self, mock_client_class, config):
        """Test TTS API with insufficient audio data."""
        mock_response = MagicMock()
        mock_response.content = b"x"  # Only 1 byte
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await send_text_to_tts_api("test", config)

        assert result is None

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_tts_timeout_error(self, mock_client_class, config):
        """Test TTS API timeout error."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await send_text_to_tts_api("test", config, timeout=0.5)

        assert result is None

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_tts_http_error(self, mock_client_class, config):
        """Test TTS API HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPStatusError(
            "Client error", request=MagicMock(), response=mock_response
        )
        mock_client_class.return_value.__aenter__.return_value = mock_client

        result = await send_text_to_tts_api("test", config)

        assert result is None

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_tts_no_token(self, mock_client_class, config):
        """Test TTS API request without token."""
        config.speech_synthesis_api_token = None

        mock_response = MagicMock()
        mock_response.content = b"audio_data_12345"
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        await send_text_to_tts_api("test", config)

        # Verify empty token header
        call_args = mock_client.post.call_args
        assert call_args[1]["headers"]["user-token"] == ""

    @patch("app.utils.speech_recognition_tools.httpx.AsyncClient")
    async def test_tts_default_sample_rate(self, mock_client_class, config):
        """Test TTS API with default sample rate."""
        mock_response = MagicMock()
        mock_response.content = b"audio_data_12345"
        mock_response.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client

        await send_text_to_tts_api("test", config)

        # Verify default sample rate
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["sample_rate"] == 16000  # noqa: PLR2004
