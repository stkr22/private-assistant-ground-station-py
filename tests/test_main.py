"""Tests for main application module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, decode_message_payload, setup_satellite_connection, websocket_endpoint


class TestUtilityFunctions:
    """Test utility functions."""

    def test_decode_message_payload_bytes(self):
        """Test decoding bytes payload."""
        payload = b"test message"
        result = decode_message_payload(payload)
        assert result == "test message"

    def test_decode_message_payload_bytearray(self):
        """Test decoding bytearray payload."""
        payload = bytearray(b"test message")
        result = decode_message_payload(payload)
        assert result == "test message"

    def test_decode_message_payload_string(self):
        """Test decoding string payload."""
        payload = "test message"
        result = decode_message_payload(payload)
        assert result == "test message"

    def test_decode_message_payload_invalid_type(self):
        """Test decoding invalid payload type."""
        payload = 12345
        result = decode_message_payload(payload)
        assert result is None

    def test_decode_message_payload_unicode(self):
        """Test decoding unicode payload."""
        payload = "test message with unicode: 你好".encode()
        result = decode_message_payload(payload)
        assert result == "test message with unicode: 你好"


class TestHTTPEndpoints:
    """Test HTTP endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200  # noqa: PLR2004
        assert response.json() == {"status": "healthy"}

    @patch("app.main.sup_util.active_connections", {})
    def test_accepts_connections_empty(self, client):
        """Test accepts connections endpoint with no active connections."""
        response = client.get("/acceptsConnections")
        assert response.status_code == 200  # noqa: PLR2004
        data = response.json()
        assert data["status"] == "ready"
        assert data["active_connections"] == 0
        assert data["max_connections"] == 50  # noqa: PLR2004

    @patch("app.main.sup_util.active_connections", {1: "ws1", 2: "ws2"})
    def test_accepts_connections_with_connections(self, client):
        """Test accepts connections endpoint with active connections."""
        response = client.get("/acceptsConnections")
        assert response.status_code == 200  # noqa: PLR2004
        data = response.json()
        assert data["status"] == "ready"
        assert data["active_connections"] == 2  # noqa: PLR2004
        assert data["max_connections"] == 50  # noqa: PLR2004


class TestWebSocketHandling:
    """Test WebSocket handling functions."""

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        return AsyncMock()

    @pytest.fixture
    def mock_sup_util(self):
        """Create mock support utilities."""
        with patch("app.main.sup_util") as mock:
            mock.mqtt_client = AsyncMock()
            mock.config_obj = MagicMock()
            mock.config_obj.broadcast_topic = "test/broadcast"
            mock.mqtt_subscription_to_queue = {}
            yield mock

    @patch("app.utils.processing_sound.SatelliteAudioProcessor")
    @patch("app.utils.client_config.ClientConfig")
    async def test_setup_satellite_connection(self, mock_client_config, mock_processor, mock_websocket, mock_sup_util):
        """Test satellite connection setup."""
        # Setup mocks
        client_config_data = {
            "samplerate": 16000,
            "input_channels": 1,
            "output_channels": 1,
            "chunk_size": 1024,
            "room": "test_room",
        }

        mock_websocket.receive_json.return_value = client_config_data

        mock_client_conf = MagicMock()
        mock_client_conf.room = "test_room"
        mock_client_conf.output_topic = "assistant/test_room/output"
        mock_client_config.model_validate.return_value = mock_client_conf

        mock_audio_processor = MagicMock()
        mock_processor.return_value = mock_audio_processor

        # Call function
        client_conf, output_queue, audio_processor = await setup_satellite_connection(mock_websocket)

        # Verify results
        assert client_conf is mock_client_conf
        assert isinstance(output_queue, asyncio.Queue)
        assert audio_processor is mock_audio_processor

        # Verify WebSocket interaction
        mock_websocket.receive_json.assert_called_once()

        # Verify MQTT subscription
        mock_sup_util.mqtt_client.subscribe.assert_called_once_with("assistant/test_room/output", qos=1)

    async def test_setup_satellite_connection_invalid_config(self, mock_websocket):
        """Test satellite connection setup with invalid config."""
        # Setup invalid config data
        mock_websocket.receive_json.return_value = {"invalid": "config"}

        with patch("app.utils.client_config.ClientConfig.model_validate") as mock_validate:
            mock_validate.side_effect = ValueError("Invalid configuration")

            with pytest.raises(ValueError):
                await setup_satellite_connection(mock_websocket)


class TestWebSocketEndpoint:
    """Test WebSocket endpoint integration."""

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket."""
        return AsyncMock()

    @patch("app.main.setup_satellite_connection")
    @patch("app.main.handle_satellite_messages")
    @patch("app.main.sup_util")
    async def test_websocket_endpoint_success(self, mock_sup_util, mock_handle_messages, mock_setup, mock_websocket):
        """Test successful WebSocket endpoint execution."""

        # Setup mocks
        mock_sup_util.active_connections = {}
        mock_client_conf = MagicMock()
        mock_client_conf.output_topic = "test/output"
        mock_output_queue = AsyncMock()
        mock_audio_processor = MagicMock()

        mock_setup.return_value = (mock_client_conf, mock_output_queue, mock_audio_processor)

        # Call endpoint
        await websocket_endpoint(mock_websocket)

        # Verify WebSocket accepted
        mock_websocket.accept.assert_called_once()

        # Note: Connection cleanup happens in finally block

        # Verify setup and message handling called
        mock_setup.assert_called_once_with(mock_websocket)
        mock_handle_messages.assert_called_once()

    @patch("app.main.sup_util")
    async def test_websocket_endpoint_duplicate_connection(self, mock_sup_util, mock_websocket):
        """Test WebSocket endpoint with duplicate connection."""

        # Setup existing connection
        connection_id = id(mock_websocket)
        mock_sup_util.active_connections = {connection_id: "existing"}

        # Call endpoint
        await websocket_endpoint(mock_websocket)

        # Verify WebSocket closed
        mock_websocket.close.assert_called_once_with(code=1001, reason="Connection already exists")

    @patch("app.main.setup_satellite_connection")
    @patch("app.main.sup_util")
    async def test_websocket_endpoint_setup_error(self, mock_sup_util, mock_setup, mock_websocket):
        """Test WebSocket endpoint with setup error."""

        # Setup mocks
        mock_sup_util.active_connections = {}
        mock_setup.side_effect = ValueError("Configuration error")

        # Call endpoint
        await websocket_endpoint(mock_websocket)

        # Verify error handling
        mock_websocket.close.assert_called_with(code=1002)

    @patch("app.main.setup_satellite_connection")
    @patch("app.main.sup_util")
    async def test_websocket_endpoint_unexpected_error(self, mock_sup_util, mock_setup, mock_websocket):
        """Test WebSocket endpoint with unexpected error."""

        # Setup mocks
        mock_sup_util.active_connections = {}
        mock_setup.side_effect = Exception("Unexpected error")

        # Call endpoint
        await websocket_endpoint(mock_websocket)

        # Verify error handling - WebSocket close is called with suppress
        # so we can't easily verify the exact call, but we can verify
        # the connection is cleaned up
        assert len(mock_sup_util.active_connections) == 0


class TestMessageDecoding:
    """Test message decoding edge cases."""

    def test_decode_empty_bytes(self):
        """Test decoding empty bytes."""
        result = decode_message_payload(b"")
        assert result == ""

    def test_decode_empty_string(self):
        """Test decoding empty string."""
        result = decode_message_payload("")
        assert result == ""

    def test_decode_none(self):
        """Test decoding None."""
        result = decode_message_payload(None)
        assert result is None

    def test_decode_invalid_utf8(self):
        """Test decoding invalid UTF-8 bytes."""
        invalid_bytes = b"\xff\xfe\xfd"
        with pytest.raises(UnicodeDecodeError):
            decode_message_payload(invalid_bytes)
