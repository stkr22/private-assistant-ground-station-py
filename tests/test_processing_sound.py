"""Tests for audio processing module."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.client_config import ClientConfig
from app.utils.config import Config
from app.utils.processing_sound import AudioConfig, ProcessingState, SatelliteAudioProcessor
from app.utils.support_utils import SupportUtils


class TestAudioConfig:
    """Test AudioConfig dataclass."""

    def test_audio_config_creation(self):
        """Test AudioConfig creation with defaults."""
        config = AudioConfig(max_frames=48000)
        
        assert config.max_frames == 48000  # noqa: PLR2004
        assert config.max_buffer_size == 1024 * 1024  # 1MB

    def test_audio_config_custom_buffer_size(self):
        """Test AudioConfig with custom buffer size."""
        config = AudioConfig(max_frames=32000, max_buffer_size=512 * 1024)
        
        assert config.max_frames == 32000  # noqa: PLR2004
        assert config.max_buffer_size == 512 * 1024


class TestSatelliteAudioProcessor:
    """Test SatelliteAudioProcessor class."""

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        return AsyncMock()

    @pytest.fixture
    def config_obj(self):
        """Create test configuration."""
        return Config(
            speech_transcription_api="http://test:8000/transcribe",
            speech_synthesis_api="http://test:8080/tts",
            max_command_input_seconds=30
        )

    @pytest.fixture
    def client_conf(self):
        """Create test client configuration."""
        return ClientConfig(
            samplerate=16000,
            input_channels=1,
            output_channels=1,
            chunk_size=1024,
            room="test_room"
        )

    @pytest.fixture
    def sup_util(self):
        """Create mock support utilities."""
        sup_util = MagicMock(spec=SupportUtils)
        sup_util.mqtt_client = AsyncMock()
        return sup_util

    @pytest.fixture
    def logger(self):
        """Create test logger."""
        return logging.getLogger("test")

    @pytest.fixture
    def processor(self, mock_websocket, config_obj, client_conf, logger, sup_util):
        """Create SatelliteAudioProcessor instance."""
        return SatelliteAudioProcessor(
            websocket=mock_websocket,
            config_obj=config_obj,
            client_conf=client_conf,
            logger=logger,
            sup_util=sup_util
        )

    def test_processor_initialization(self, processor):
        """Test processor initialization."""
        assert processor.state == ProcessingState.IDLE
        assert processor.audio_buffer == []
        assert processor._buffer_size_bytes == 0

    async def test_start_audio_collection(self, processor):
        """Test starting audio collection."""
        await processor.handle_control_signal("START_COMMAND")
        
        assert processor.state == ProcessingState.COLLECTING_AUDIO
        assert processor.audio_buffer == []
        assert processor._buffer_size_bytes == 0

    async def test_start_audio_collection_when_not_idle(self, processor, logger):
        """Test starting audio collection when not idle."""
        processor.state = ProcessingState.PROCESSING_STT
        
        with patch.object(logger, 'warning') as mock_warning:
            await processor.handle_control_signal("START_COMMAND")
            mock_warning.assert_called_once()
        
        assert processor.state == ProcessingState.PROCESSING_STT

    async def test_cancel_processing(self, processor):
        """Test canceling audio processing."""
        processor.state = ProcessingState.COLLECTING_AUDIO
        processor.audio_buffer = [b"test"]
        processor._buffer_size_bytes = 4
        
        await processor.handle_control_signal("CANCEL_COMMAND")
        
        assert processor.state == ProcessingState.IDLE
        assert processor.audio_buffer == []
        assert processor._buffer_size_bytes == 0

    async def test_handle_audio_data_when_collecting(self, processor):
        """Test handling audio data during collection."""
        await processor.handle_control_signal("START_COMMAND")
        
        audio_data = b"test_audio_data"
        await processor.handle_audio_data(audio_data)
        
        assert len(processor.audio_buffer) == 1
        assert processor.audio_buffer[0] == audio_data
        assert processor._buffer_size_bytes == len(audio_data)

    async def test_handle_audio_data_when_not_collecting(self, processor, logger):
        """Test handling audio data when not collecting."""
        with patch.object(logger, 'warning') as mock_warning:
            await processor.handle_audio_data(b"test")
            mock_warning.assert_called_once()
        
        assert len(processor.audio_buffer) == 0

    async def test_audio_buffer_size_limit(self, processor):
        """Test audio buffer size limit handling."""
        await processor.handle_control_signal("START_COMMAND")
        
        # Set a small buffer size for testing
        processor.audio_config.max_buffer_size = 10
        
        with patch.object(processor, '_process_collected_audio') as mock_process:
            # Add data that exceeds buffer limit
            await processor.handle_audio_data(b"12345678901234567890")
            mock_process.assert_called_once()

    def test_generate_error_beep(self, processor):
        """Test error beep generation."""
        beep_data = processor._generate_error_beep(duration=0.1, frequency=1000)
        
        assert isinstance(beep_data, bytes)
        assert len(beep_data) > 0
        
        # Should be 16-bit audio (2 bytes per sample)
        expected_samples = int(processor.client_conf.samplerate * 0.1)
        expected_bytes = expected_samples * 2
        assert len(beep_data) == expected_bytes

    async def test_send_error_feedback(self, processor, mock_websocket):
        """Test sending error feedback."""
        await processor._send_error_feedback()
        
        mock_websocket.send_bytes.assert_called_once()
        # Verify that bytes were sent
        call_args = mock_websocket.send_bytes.call_args[0]
        assert isinstance(call_args[0], bytes)

    async def test_send_error_feedback_exception(self, processor, mock_websocket, logger):
        """Test error feedback when WebSocket fails."""
        mock_websocket.send_bytes.side_effect = Exception("WebSocket error")
        
        with patch.object(logger, 'error') as mock_error:
            await processor._send_error_feedback()
            mock_error.assert_called_once()

    @patch('app.utils.processing_sound.srt.send_audio_to_stt_api')
    async def test_process_collected_audio_success(self, mock_stt, processor, sup_util):
        """Test successful audio processing."""
        # Setup
        await processor.handle_control_signal("START_COMMAND")
        await processor.handle_audio_data(b"audio_data_1")
        await processor.handle_audio_data(b"audio_data_2")
        
        # Mock STT response
        mock_response = MagicMock()
        mock_response.text = "test transcription"
        mock_stt.return_value = mock_response
        
        # Process audio
        await processor._process_collected_audio()
        
        # Verify STT was called
        mock_stt.assert_called_once()
        
        # Verify MQTT publish was called
        sup_util.mqtt_client.publish.assert_called_once()
        
        # Verify state reset
        assert processor.state == ProcessingState.IDLE
        assert processor.audio_buffer == []
        assert processor._buffer_size_bytes == 0

    @patch('app.utils.processing_sound.srt.send_audio_to_stt_api')
    async def test_process_collected_audio_stt_failure(self, mock_stt, processor):
        """Test audio processing with STT failure."""
        # Setup
        await processor.handle_control_signal("START_COMMAND")
        await processor.handle_audio_data(b"audio_data")
        
        # Mock STT failure
        mock_stt.return_value = None
        
        with patch.object(processor, '_send_error_feedback') as mock_error:
            await processor._process_collected_audio()
            mock_error.assert_called_once()

    async def test_process_empty_audio_buffer(self, processor, logger):
        """Test processing empty audio buffer."""
        with patch.object(logger, 'warning') as mock_warning:
            await processor._process_collected_audio()
            mock_warning.assert_called_once()
        
        assert processor.state == ProcessingState.IDLE

    async def test_unknown_control_signal(self, processor, logger):
        """Test handling unknown control signal."""
        with patch.object(logger, 'warning') as mock_warning:
            await processor.handle_control_signal("UNKNOWN_SIGNAL")
            mock_warning.assert_called_once()

    async def test_max_audio_duration_exceeded(self, processor):
        """Test handling when maximum audio duration is exceeded."""
        await processor.handle_control_signal("START_COMMAND")
        
        # Create audio data that exceeds max duration
        # Each sample is 2 bytes (16-bit), so for 30 seconds at 16kHz = 30 * 16000 * 2 bytes
        max_samples = processor.audio_config.max_frames
        large_audio = b"x" * (max_samples * 2 + 100)  # Exceed by 50 samples
        
        with patch.object(processor, '_process_collected_audio') as mock_process:
            await processor.handle_audio_data(large_audio)
            mock_process.assert_called_once()

    async def test_end_command_when_not_collecting(self, processor, logger):
        """Test END_COMMAND when not currently collecting audio."""
        with patch.object(logger, 'warning') as mock_warning:
            await processor.handle_control_signal("END_COMMAND")
            mock_warning.assert_called_once()