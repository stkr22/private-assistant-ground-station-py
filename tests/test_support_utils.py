"""Tests for support utilities module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.utils.config import Config
from app.utils.support_utils import SupportUtils


class TestSupportUtils:
    """Test SupportUtils class."""

    @pytest.fixture
    def support_utils(self):
        """Create SupportUtils instance."""
        return SupportUtils()

    def test_initialization(self, support_utils):
        """Test SupportUtils initialization."""
        assert support_utils._config_obj is None
        assert support_utils._mqtt_client is None
        assert support_utils.mqtt_subscription_to_queue == {}
        assert support_utils.active_connections == {}

    def test_config_obj_property_not_set(self, support_utils):
        """Test config_obj property when not set."""
        with pytest.raises(ValueError, match="Config object is not set"):
            _ = support_utils.config_obj

    def test_config_obj_property_set(self, support_utils):
        """Test config_obj property when set."""
        config = Config()
        support_utils.config_obj = config
        
        assert support_utils.config_obj is config

    def test_mqtt_client_property_not_set(self, support_utils):
        """Test mqtt_client property when not set."""
        with pytest.raises(ValueError, match="MQTT client is not set"):
            _ = support_utils.mqtt_client

    def test_mqtt_client_property_set(self, support_utils):
        """Test mqtt_client property when set."""
        mock_client = AsyncMock()
        support_utils.mqtt_client = mock_client
        
        assert support_utils.mqtt_client is mock_client

    def test_mqtt_subscription_management(self, support_utils):
        """Test MQTT subscription queue management."""
        # Add subscription
        queue = asyncio.Queue()
        topic = "test/topic"
        support_utils.mqtt_subscription_to_queue[topic] = queue
        
        assert topic in support_utils.mqtt_subscription_to_queue
        assert support_utils.mqtt_subscription_to_queue[topic] is queue

    def test_active_connections_management(self, support_utils):
        """Test active connections management."""
        # Add connection
        mock_websocket = MagicMock()
        connection_id = 12345
        support_utils.active_connections[connection_id] = mock_websocket
        
        assert connection_id in support_utils.active_connections
        assert support_utils.active_connections[connection_id] is mock_websocket
        
        # Remove connection
        del support_utils.active_connections[connection_id]
        assert connection_id not in support_utils.active_connections

    def test_multiple_connections(self, support_utils):
        """Test handling multiple active connections."""
        # Add multiple connections
        connections = {}
        for i in range(5):
            mock_websocket = MagicMock()
            connection_id = i
            support_utils.active_connections[connection_id] = mock_websocket
            connections[connection_id] = mock_websocket
        
        assert len(support_utils.active_connections) == 5
        
        # Verify all connections are present
        for connection_id, websocket in connections.items():
            assert support_utils.active_connections[connection_id] is websocket

    def test_multiple_subscriptions(self, support_utils):
        """Test handling multiple MQTT subscriptions."""
        # Add multiple subscriptions
        subscriptions = {}
        for i in range(3):
            queue = asyncio.Queue()
            topic = f"test/topic/{i}"
            support_utils.mqtt_subscription_to_queue[topic] = queue
            subscriptions[topic] = queue
        
        assert len(support_utils.mqtt_subscription_to_queue) == 3
        
        # Verify all subscriptions are present
        for topic, queue in subscriptions.items():
            assert support_utils.mqtt_subscription_to_queue[topic] is queue

    def test_config_and_client_integration(self, support_utils):
        """Test setting both config and MQTT client."""
        config = Config(mqtt_server_host="test-host", mqtt_server_port=9999)
        mock_client = AsyncMock()
        
        support_utils.config_obj = config
        support_utils.mqtt_client = mock_client
        
        assert support_utils.config_obj.mqtt_server_host == "test-host"
        assert support_utils.config_obj.mqtt_server_port == 9999
        assert support_utils.mqtt_client is mock_client