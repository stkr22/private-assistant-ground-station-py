"""Tests for main application module."""

import asyncio
import logging
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, decode_message_payload, listen, setup_satellite_connection, sup_util, websocket_endpoint


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


class TestListenFunction:
    """Test listen function for MQTT message handling."""

    @pytest.fixture
    def mock_mqtt_client(self):
        """Create mock MQTT client."""
        return AsyncMock()

    @pytest.fixture
    def mock_sup_util(self):
        """Create mock support utilities."""
        mock = MagicMock()
        mock.config_obj = MagicMock()
        mock.config_obj.broadcast_topic = "assistant/broadcast"
        mock.mqtt_subscription_to_queue = {}
        return mock

    @pytest.fixture
    def mock_message(self):
        """Create mock MQTT message."""
        message = MagicMock()
        message.topic = MagicMock()
        return message

    async def test_listen_broadcast_with_satellites(self, mock_mqtt_client, mock_sup_util, mock_message):
        """Test broadcast message forwarded to all connected satellites."""
        # Setup satellite queues
        queue1 = asyncio.Queue()
        queue2 = asyncio.Queue()
        mock_sup_util.mqtt_subscription_to_queue = {
            "assistant/room1/output": queue1,
            "assistant/room2/output": queue2,
        }

        # Setup broadcast message
        mock_message.topic.value = "assistant/broadcast"
        mock_message.payload = b'{"text": "test broadcast", "alert": null}'

        # Mock client.messages to yield one message then stop
        async def mock_messages():
            yield mock_message

        mock_mqtt_client.messages = mock_messages()

        # Run listen (will process one message then exit)
        with suppress(TimeoutError):
            await asyncio.wait_for(listen(mock_mqtt_client, mock_sup_util), timeout=0.1)

        # Verify message was forwarded to both satellites
        assert queue1.qsize() == 1
        assert queue2.qsize() == 1

        response1 = await queue1.get()
        response2 = await queue2.get()
        assert response1.text == "test broadcast"
        assert response2.text == "test broadcast"

    async def test_listen_broadcast_no_satellites(self, mock_mqtt_client, mock_sup_util, mock_message, caplog):
        """Test broadcast message with no satellites connected logs debug message."""
        # No satellite queues
        mock_sup_util.mqtt_subscription_to_queue = {}

        # Setup broadcast message
        mock_message.topic.value = "assistant/broadcast"
        mock_message.payload = b'{"text": "test broadcast", "alert": null}'

        async def mock_messages():
            yield mock_message

        mock_mqtt_client.messages = mock_messages()

        with caplog.at_level(logging.DEBUG), suppress(TimeoutError):
            await asyncio.wait_for(listen(mock_mqtt_client, mock_sup_util), timeout=0.1)

        # Verify debug message logged (not warning)
        assert "no satellites connected" in caplog.text
        assert caplog.records[0].levelname == "DEBUG"

    async def test_listen_broadcast_invalid_json(self, mock_mqtt_client, mock_sup_util, mock_message, caplog):
        """Test broadcast message with invalid JSON logs error."""
        # Setup satellite queue
        queue1 = asyncio.Queue()
        mock_sup_util.mqtt_subscription_to_queue = {"assistant/room1/output": queue1}

        # Setup invalid broadcast message
        mock_message.topic.value = "assistant/broadcast"
        mock_message.payload = b"invalid json"

        async def mock_messages():
            yield mock_message

        mock_mqtt_client.messages = mock_messages()

        with caplog.at_level(logging.ERROR), suppress(TimeoutError):
            await asyncio.wait_for(listen(mock_mqtt_client, mock_sup_util), timeout=0.1)

        # Verify error logged and message not forwarded
        assert "failed validation" in caplog.text.lower()
        assert queue1.qsize() == 0

    async def test_listen_non_broadcast_message(self, mock_mqtt_client, mock_sup_util, mock_message):
        """Test non-broadcast message uses normal queue lookup."""
        # Setup room-specific queue
        room_queue = asyncio.Queue()
        mock_sup_util.mqtt_subscription_to_queue = {"assistant/room1/output": room_queue}

        # Setup non-broadcast message
        mock_message.topic.value = "assistant/room1/output"
        mock_message.payload = b'{"text": "room message", "alert": null}'

        async def mock_messages():
            yield mock_message

        mock_mqtt_client.messages = mock_messages()

        with suppress(TimeoutError):
            await asyncio.wait_for(listen(mock_mqtt_client, mock_sup_util), timeout=0.1)

        # Verify message went to correct queue
        assert room_queue.qsize() == 1
        response = await room_queue.get()
        assert response.text == "room message"

    async def test_listen_non_broadcast_no_queue(self, mock_mqtt_client, mock_sup_util, mock_message, caplog):
        """Test non-broadcast message with no queue logs warning."""
        # No queues registered
        mock_sup_util.mqtt_subscription_to_queue = {}

        # Setup non-broadcast message for unknown topic
        mock_message.topic.value = "assistant/unknown/output"
        mock_message.payload = b'{"text": "test", "alert": null}'

        async def mock_messages():
            yield mock_message

        mock_mqtt_client.messages = mock_messages()

        with caplog.at_level(logging.WARNING), suppress(TimeoutError):
            await asyncio.wait_for(listen(mock_mqtt_client, mock_sup_util), timeout=0.1)

        # Verify warning logged for unknown topic
        assert "seems to have no queue" in caplog.text
        assert caplog.records[0].levelname == "WARNING"


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

    @patch("app.main.sup_util.mqtt_connected", True)
    def test_put_text_message_success(self, client):
        """Test successful PUT /text endpoint."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.text_endpoint_auth_token = "TEST_TOKEN"
        mock_config.input_topic = "assistant/ground_station/input"
        mock_config.broadcast_topic = "assistant/ground_station/broadcast"
        sup_util._config_obj = mock_config

        mock_mqtt_client = AsyncMock()
        mock_mqtt_client.publish = AsyncMock()
        sup_util._mqtt_client = mock_mqtt_client

        # Make request
        response = client.put(
            "/text",
            json={"text": "test message", "device_id": "test_device"},
            headers={"Authorization": "Bearer TEST_TOKEN"},
        )

        # Verify response
        assert response.status_code == 200  # noqa: PLR2004
        data = response.json()
        assert data["status"] == "accepted"
        assert "request_id" in data
        assert len(data["request_id"]) > 0

    def test_put_text_message_missing_auth(self, client):
        """Test PUT /text endpoint with missing Authorization header."""
        response = client.put(
            "/text",
            json={"text": "test message", "device_id": "test_device"},
        )

        assert response.status_code == 401  # noqa: PLR2004
        assert response.json()["detail"] == "Missing Authorization header"

    def test_put_text_message_invalid_token(self, client):
        """Test PUT /text endpoint with invalid token."""
        mock_config = MagicMock()
        mock_config.text_endpoint_auth_token = "CORRECT_TOKEN"
        sup_util._config_obj = mock_config

        response = client.put(
            "/text",
            json={"text": "test message", "device_id": "test_device"},
            headers={"Authorization": "Bearer WRONG_TOKEN"},
        )

        assert response.status_code == 401  # noqa: PLR2004
        assert response.json()["detail"] == "Invalid authentication token"

    @patch("app.main.sup_util.mqtt_connected", False)
    def test_put_text_message_mqtt_unavailable(self, client):
        """Test PUT /text endpoint when MQTT is unavailable."""
        mock_config = MagicMock()
        mock_config.text_endpoint_auth_token = "TEST_TOKEN"
        sup_util._config_obj = mock_config

        response = client.put(
            "/text",
            json={"text": "test message", "device_id": "test_device"},
            headers={"Authorization": "Bearer TEST_TOKEN"},
        )

        assert response.status_code == 503  # noqa: PLR2004
        assert response.json()["detail"] == "MQTT broker unavailable"

    @patch("app.main.sup_util.mqtt_connected", True)
    def test_put_text_message_mqtt_publish_failure(self, client):
        """Test PUT /text endpoint when MQTT publish fails."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.text_endpoint_auth_token = "TEST_TOKEN"
        mock_config.input_topic = "assistant/ground_station/input"
        mock_config.broadcast_topic = "assistant/ground_station/broadcast"
        sup_util._config_obj = mock_config

        mock_mqtt_client = AsyncMock()
        mock_mqtt_client.publish = AsyncMock(side_effect=Exception("MQTT publish failed"))
        sup_util._mqtt_client = mock_mqtt_client

        # Make request
        response = client.put(
            "/text",
            json={"text": "test message", "device_id": "test_device"},
            headers={"Authorization": "Bearer TEST_TOKEN"},
        )

        # Verify response
        assert response.status_code == 503  # noqa: PLR2004
        assert "Failed to publish message to MQTT broker" in response.json()["detail"]

    @patch("app.main.sup_util.mqtt_connected", True)
    def test_put_text_message_bearer_prefix_handling(self, client):
        """Test PUT /text endpoint handles various Bearer token formats."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.text_endpoint_auth_token = "TEST_TOKEN"
        mock_config.input_topic = "assistant/ground_station/input"
        mock_config.broadcast_topic = "assistant/ground_station/broadcast"
        sup_util._config_obj = mock_config

        mock_mqtt_client = AsyncMock()
        mock_mqtt_client.publish = AsyncMock()
        sup_util._mqtt_client = mock_mqtt_client

        # Test with extra spaces
        response = client.put(
            "/text",
            json={"text": "test message", "device_id": "test_device"},
            headers={"Authorization": "Bearer  TEST_TOKEN  "},
        )

        assert response.status_code == 200  # noqa: PLR2004

    def test_put_text_message_invalid_request_body(self, client):
        """Test PUT /text endpoint with invalid request body."""
        response = client.put(
            "/text",
            json={"text": "test message"},  # missing device_id
            headers={"Authorization": "Bearer TEST_TOKEN"},
        )

        assert response.status_code == 422  # noqa: PLR2004  # Unprocessable Entity


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
