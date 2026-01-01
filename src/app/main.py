#!/usr/bin/env python3

import asyncio
import logging
import os
import pathlib
import sys
import uuid
from contextlib import asynccontextmanager, suppress

import aiomqtt
import pydantic
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from private_assistant_commons import MqttConfig, messages

from app.utils import (
    client_config,
    config,
    models,
    processing_sound,
    speech_recognition_tools,
    support_utils,
)

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

sup_util = support_utils.SupportUtils()


def decode_message_payload(payload) -> str | None:
    """Decode the message payload if it is a suitable type."""
    if isinstance(payload, bytes | bytearray):
        return payload.decode("utf-8")
    if isinstance(payload, str):
        return payload
    logger.warning("Unexpected payload type: %s", type(payload))
    return None


async def listen(client: aiomqtt.Client, sup_util: support_utils.SupportUtils):
    """
    Listen for MQTT messages and route them to appropriate queues.

    Note: If connection is lost during iteration, aiomqtt.MqttError will be raised
    and caught by the reconnection loop in lifespan().
    """
    async for message in client.messages:
        logger.debug("Received message: %s", message)

        # Handle broadcast messages specially - forward to all connected satellites
        if message.topic.value == sup_util.config_obj.broadcast_topic:
            payload_str = decode_message_payload(message.payload)
            if payload_str is not None:
                # Get all satellite queues (topics ending with /output)
                satellite_queues = [
                    (topic, queue)
                    for topic, queue in sup_util.mqtt_subscription_to_queue.items()
                    if topic.endswith("/output")
                ]

                if satellite_queues:
                    try:
                        response = messages.Response.model_validate_json(payload_str)
                        for _, queue in satellite_queues:
                            await queue.put(response)
                        logger.info("Broadcast message forwarded to %d satellite(s)", len(satellite_queues))
                    except pydantic.ValidationError:
                        logger.error("Broadcast message failed validation. %s", payload_str)
                else:
                    logger.debug("Broadcast message received but no satellites connected")
            continue

        # Normal queue lookup for non-broadcast messages
        topic_queue = sup_util.mqtt_subscription_to_queue.get(message.topic.value)
        if topic_queue is None:
            logger.warning("%s seems to have no queue. Discarding message.", message.topic)
        else:
            payload_str = decode_message_payload(message.payload)
            if payload_str is not None:
                try:
                    await topic_queue.put(messages.Response.model_validate_json(payload_str))
                except pydantic.ValidationError:
                    logger.error("Message failed validation. %s", payload_str)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # Load app config from YAML
    sup_util.config_obj = config.load_config(
        pathlib.Path(os.getenv("PRIVATE_ASSISTANT_API_CONFIG_PATH", "local_config.yaml"))
    )

    # Load MQTT config from environment variables (with defaults)
    sup_util.mqtt_config = MqttConfig(host="localhost", port=1883)

    # AIDEV-NOTE: Reconnection loop with exponential backoff for MQTT resilience
    reconnect_delay = 5  # Initial delay in seconds
    max_reconnect_delay = 60  # Maximum delay in seconds
    task = None

    async def connect_and_listen():
        """Connect to MQTT and listen for messages with automatic reconnection."""
        nonlocal reconnect_delay

        while True:
            try:
                logger.info(
                    "Connecting to MQTT broker at %s:%s",
                    sup_util.mqtt_config.host,
                    sup_util.mqtt_config.port,
                )

                async with aiomqtt.Client(
                    hostname=sup_util.mqtt_config.host,
                    port=sup_util.mqtt_config.port,
                    username=sup_util.mqtt_config.username,
                    password=sup_util.mqtt_config.password,
                ) as client:
                    # Make client globally available
                    sup_util.mqtt_client = client
                    sup_util.mqtt_connected = True

                    # Subscribe to broadcast topic
                    await client.subscribe(sup_util.config_obj.broadcast_topic, qos=1)
                    logger.info("MQTT connected successfully")
                    reconnect_delay = 5  # Reset backoff on successful connection

                    # Listen for messages
                    await listen(client, sup_util=sup_util)

            except aiomqtt.MqttError as e:
                sup_util.mqtt_connected = False
                logger.error("MQTT connection lost: %s. Reconnecting in %s seconds...", e, reconnect_delay)

                # Close all active WebSocket connections
                connections_to_close = list(sup_util.active_connections.values())
                for websocket in connections_to_close:
                    try:
                        await websocket.close(code=1011, reason="MQTT connection lost")
                        logger.info("Closed WebSocket connection due to MQTT disconnect")
                    except Exception as close_error:
                        logger.warning("Error closing WebSocket: %s", close_error)

                await asyncio.sleep(reconnect_delay)
                # Exponential backoff with maximum limit
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    # Start the connection task
    loop = asyncio.get_event_loop()
    task = loop.create_task(connect_and_listen())

    try:
        yield
    finally:
        # Cancel the task on shutdown
        if task:
            task.cancel()
            # Wait for the task to be cancelled
            with suppress(asyncio.CancelledError):
                await task
        sup_util.mqtt_connected = False


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}


@app.get("/acceptsConnections")
async def accepts_connection():
    """Endpoint to check if the app can accept new WebSocket connections."""
    return {
        "status": "ready",
        "active_connections": len(sup_util.active_connections),
        "max_connections": 50,  # Configurable limit
    }


@app.put("/text")
async def put_text_message(
    request: models.TextMessageRequest,
    authorization: str | None = Header(None),
) -> models.TextMessageResponse:
    """
    Accept transcribed text from external devices (e.g., Apple Watch).

    Publishes the text to MQTT with the broadcast topic as output_topic,
    allowing any WebSocket-connected devices at home to receive the response.

    Args:
        request: The text message request containing text and device_id
        authorization: Bearer token for authentication

    Returns:
        TextMessageResponse with status and request_id for tracking

    Raises:
        HTTPException: 401 if unauthorized, 503 if MQTT unavailable
    """
    # Validate authentication token
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Extract token from "Bearer <token>" format
    token = authorization.removeprefix("Bearer ").strip()
    if token != sup_util.config_obj.text_endpoint_auth_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    # Check MQTT connection
    if not sup_util.mqtt_connected:
        raise HTTPException(status_code=503, detail="MQTT broker unavailable")

    # Generate unique request ID
    request_id = uuid.uuid4()

    # Create MQTT request with broadcast topic as output
    mqtt_request = messages.ClientRequest(
        id=request_id,
        text=request.text,
        room=request.device_id,  # Use device_id as room identifier
        output_topic=sup_util.config_obj.remote_broadcast_topic
        if request.remote
        else sup_util.config_obj.broadcast_topic,
    )

    # Publish to MQTT input topic
    try:
        await sup_util.mqtt_client.publish(
            sup_util.config_obj.input_topic,
            mqtt_request.model_dump_json(),
            qos=1,
        )
        logger.info(
            "Published text message from device %s (request_id: %s)",
            request.device_id,
            request_id,
        )
    except Exception as e:
        logger.error("Failed to publish MQTT message: %s", e)
        raise HTTPException(status_code=503, detail="Failed to publish message to MQTT broker") from e

    # Return immediately - response will be broadcast to WebSocket clients
    return models.TextMessageResponse(
        status="accepted",
        request_id=str(request_id),
    )


async def setup_satellite_connection(websocket: WebSocket):
    """Setup MQTT and audio processor for satellite connection."""
    client_config_raw = await websocket.receive_json()
    client_conf = client_config.ClientConfig.model_validate(client_config_raw)

    # Setup MQTT subscription for this client
    output_queue: asyncio.Queue[messages.Response] = asyncio.Queue()
    output_topic = f"assistant/{client_conf.room}/output"
    client_conf.output_topic = output_topic
    sup_util.mqtt_subscription_to_queue[output_topic] = output_queue

    # Subscribe to client-specific topic (MQTT is guaranteed to be connected)
    await sup_util.mqtt_client.subscribe(output_topic, qos=1)

    sup_util.mqtt_subscription_to_queue[sup_util.config_obj.broadcast_topic] = output_queue

    # AIDEV-NOTE: New ground station protocol - handle satellite communication
    audio_processor = processing_sound.SatelliteAudioProcessor(
        websocket=websocket, config_obj=sup_util.config_obj, client_conf=client_conf, logger=logger, sup_util=sup_util
    )

    return client_conf, output_queue, audio_processor


async def handle_satellite_messages(websocket: WebSocket, audio_processor, output_queue, client_conf):
    """Handle satellite WebSocket messages and MQTT responses."""

    async def handle_mqtt_responses():
        while True:
            try:
                await process_output_queue(websocket, output_queue, sup_util.config_obj, client_conf)
                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
            except Exception as e:
                logger.error("Error processing MQTT responses: %s", e)
                break

    # Start MQTT response handler
    mqtt_task = asyncio.create_task(handle_mqtt_responses())

    try:
        # Main message loop
        while True:
            message = await websocket.receive()

            # Handle disconnect message explicitly
            if message.get("type") == "websocket.disconnect":
                logger.info("Received disconnect message from WebSocket")
                break

            if "text" in message:
                text_message = message["text"]
                # Handle control signals from satellite
                await audio_processor.handle_control_signal(text_message)

            elif "bytes" in message:
                # Handle audio data from satellite
                audio_bytes = message["bytes"]
                await audio_processor.handle_audio_data(audio_bytes)

    except RuntimeError as e:
        # Handle "Cannot call receive once a disconnect message has been received"
        if "disconnect message has been received" in str(e):
            logger.info("WebSocket disconnected, stopping message loop")
        else:
            raise
    finally:
        mqtt_task.cancel()
        with suppress(asyncio.CancelledError):
            await mqtt_task


@app.websocket("/satellite")
async def websocket_endpoint(websocket: WebSocket):
    connection_id = id(websocket)
    if connection_id in sup_util.active_connections:
        await websocket.close(code=1001, reason="Connection already exists")
        return

    await websocket.accept()

    # Check if MQTT is connected before allowing WebSocket connection
    if not sup_util.mqtt_connected:
        logger.warning("Rejecting WebSocket connection: MQTT not connected")
        await websocket.close(code=1011, reason="MQTT broker unavailable")
        return

    sup_util.active_connections[connection_id] = websocket
    output_topic = None
    client_room = None

    try:
        client_conf, output_queue, audio_processor = await setup_satellite_connection(websocket)
        output_topic = client_conf.output_topic
        client_room = client_conf.room
        logger.info("Satellite connected: room=%s, topic=%s", client_room, output_topic)
        await handle_satellite_messages(websocket, audio_processor, output_queue, client_conf)

    except WebSocketDisconnect:
        logger.info("Satellite disconnected: room=%s", client_room or "unknown")
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        with suppress(Exception):
            await websocket.close(code=1002)
    except Exception as e:
        logger.exception("Unexpected error occurred: %s", e)
        with suppress(Exception):
            await websocket.close(code=1011)
    finally:
        # AIDEV-NOTE: Cleanup connection state to prevent stale references and queue buildup
        # Remove from active connections immediately
        if connection_id in sup_util.active_connections:
            del sup_util.active_connections[connection_id]
            logger.debug("Removed connection %s from active connections", connection_id)

        # Cleanup MQTT subscription queue mapping for satellite-specific topic
        if output_topic and output_topic in sup_util.mqtt_subscription_to_queue:
            del sup_util.mqtt_subscription_to_queue[output_topic]
            logger.debug("Removed MQTT queue mapping for topic: %s", output_topic)

        logger.info(
            "Satellite cleanup complete: room=%s, active_connections=%d",
            client_room or "unknown",
            len(sup_util.active_connections),
        )


async def process_output_queue(
    websocket: WebSocket,
    output_queue: asyncio.Queue[messages.Response],
    config_obj: config.Config,
    client_conf: client_config.ClientConfig,
):
    # AIDEV-NOTE: Optimized to process all available messages to reduce queue buildup
    processed_count = 0
    max_process_per_cycle = 3  # Limit processing to prevent blocking audio

    try:
        while processed_count < max_process_per_cycle:
            response = output_queue.get_nowait()

            # Validate WebSocket is still connected before sending
            try:
                audio_bytes = await speech_recognition_tools.send_text_to_tts_api(
                    response.text, config_obj, sample_rate=client_conf.samplerate
                )
                if response.alert is not None and response.alert.play_before:
                    await websocket.send_text("alert_default")
                if audio_bytes is not None:
                    await websocket.send_bytes(audio_bytes)
                processed_count += 1
            except (WebSocketDisconnect, RuntimeError) as e:
                # Connection closed while processing, stop sending
                logger.debug("WebSocket disconnected during send: %s", e)
                break

    except asyncio.QueueEmpty:
        if processed_count > 0:
            logger.debug("Processed %d messages from output queue", processed_count)
        # No more messages to process
