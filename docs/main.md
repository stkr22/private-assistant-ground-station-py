# Private Assistant Ground Station Documentation

## Overview

The Private Assistant Ground Station is a centralized audio processing hub that serves multiple satellite devices in a smart assistant ecosystem. Unlike the previous comms-bridge architecture, the ground station focuses solely on STT/TTS processing and MQTT communication, while satellites handle wake word detection and silence detection.

## Architecture Changes

### From Comms Bridge to Ground Station

**Previous (Comms Bridge):**
- Single client connection
- Wake word detection on server
- Voice activity detection on server
- Audio streaming for wake word detection

**Current (Ground Station):**
- Multiple satellite connections
- Wake word detection on satellites
- No VAD processing on ground station  
- Audio buffering only after wake word detected

## WebSocket Protocol

### Endpoint: `/satellite`

The ground station accepts satellite connections on the `/satellite` WebSocket endpoint.

### Message Types

#### 1. Configuration (JSON)
First message from satellite must be client configuration:
```json
{
  "samplerate": 16000,
  "input_channels": 1,
  "output_channels": 1,
  "chunk_size": 1024,
  "room": "living_room"
}
```

#### 2. Control Signals (Text Messages)
- `START_COMMAND` - Satellite detected wake word, audio stream starting
- `END_COMMAND` - Satellite detected silence, process buffered audio
- `CANCEL_COMMAND` - Cancel current processing (optional)

#### 3. Audio Data (Binary Messages)
- 16kHz, 16-bit PCM audio data
- Sent only between START_COMMAND and END_COMMAND
- Buffered by ground station until END_COMMAND

#### 4. Response Messages (from Ground Station)
- `alert_default` - Alert tone before TTS response
- `error_beep` - Error occurred during processing
- Binary audio data - TTS response audio

## Configuration

The ground station uses two separate configuration sources:
1. **Application Config (YAML)** - Ground station-specific settings
2. **MQTT Config (Environment Variables)** - MQTT broker connection settings

### Application Config (YAML)

Configuration file specified via `PRIVATE_ASSISTANT_API_CONFIG_PATH` environment variable (defaults to `local_config.yaml`):

```yaml
# Speech API endpoints
speech_transcription_api: "http://localhost:8000/transcribe"
speech_transcription_api_token: null
speech_synthesis_api: "http://localhost:8080/synthesizeSpeech"
speech_synthesis_api_token: null

# Client identification
client_id: "ground-station-01"  # Defaults to hostname if not specified

# Ground station settings
max_command_input_seconds: 30

# Topic overrides (optional)
remote_broadcast_topic: "assistant/ground_station/remote_broadcast"
client_topic_overwrite: null  # Override computed client_topic
input_topic_overwrite: null
output_topic_overwrite: null

# Authentication
text_endpoint_auth_token: "DEBUG"
```

### MQTT Configuration (Environment Variables)

MQTT broker connection settings are configured via environment variables:

```bash
export MQTT_HOST=localhost        # MQTT broker hostname
export MQTT_PORT=1883            # MQTT broker port
export MQTT_USERNAME=user        # Optional: authentication username
export MQTT_PASSWORD=pass        # Optional: authentication password
```

**Defaults** (used when environment variables are not set):
- `MQTT_HOST`: localhost
- `MQTT_PORT`: 1883
- `MQTT_USERNAME`: null
- `MQTT_PASSWORD`: null

### Inherited Configuration from Commons

Ground station extends `private-assistant-commons.SkillConfig` and inherits:
- `broadcast_topic`: "assistant/broadcast" (used for forwarding messages to all satellites)
- `intent_analysis_result_topic`: "assistant/intent_engine/result"
- `device_update_topic`: "assistant/global_device_update"
- `intent_cache_size`: 1000

### Removed Configuration Options

These options were removed as they're no longer needed:
- `wakework_detection_threshold` - Wake word detection on satellites
- `openwakeword_inference_framework` - No wake word processing
- `path_or_name_wakeword_model` - No wake word models
- `name_wakeword_model` - No wake word processing
- `max_length_speech_pause` - Silence detection on satellites
- `vad_threshold` - No VAD processing

## MQTT Topics

### Topic Structure
- Input: `assistant/ground_station/all/{client_id}/input`
- Output: `assistant/{room}/output`
- Broadcast: `assistant/broadcast` (inherited from commons.SkillConfig)
- Remote Broadcast: `assistant/ground_station/remote_broadcast`

### Message Format
Ground station publishes `ClientRequest` messages to MQTT:
```json
{
  "id": "uuid-here",
  "text": "transcribed speech text",
  "room": "living_room", 
  "output_topic": "assistant/living_room/output"
}
```

## Error Handling

### Processing Failures
- STT API failures trigger `error_beep` signal to satellite
- MQTT publishing failures are logged
- WebSocket disconnections are handled gracefully

### Buffer Management
- Maximum buffer size: 1MB
- Maximum audio duration: 30 seconds (configurable)
- Automatic processing when limits exceeded

## Multiple Satellite Support

The ground station supports multiple concurrent satellite connections:
- Each satellite gets its own MQTT topic subscription
- Audio processing is handled per-satellite
- Room-based message routing
- Independent error handling per connection

## Performance Considerations

### Advantages over Comms Bridge
- **Reduced Processing Load**: No wake word/VAD processing
- **Better Scalability**: Multiple satellite support
- **Lower Latency**: No continuous audio analysis
- **Resource Efficiency**: Centralized STT/TTS processing

### Limitations
- **Network Dependency**: Requires reliable connection to satellites
- **Audio Buffering**: Slight delay due to buffering requirement  
- **Single Point of Failure**: All satellites depend on ground station

## Development Notes

### Dependencies Removed
- `openWakeWord` - Wake word detection library
- `pysilero-vad` - Voice activity detection
- `onnxruntime` - ONNX inference runtime
- `speexdsp-ns` - Noise suppression

### Code Changes
- Removed `silero_vad.py` module
- Replaced `AudioProcessor` with `SatelliteAudioProcessor`
- Updated WebSocket endpoint from `/client_control` to `/satellite`
- Simplified configuration model
- Added multi-connection support in `SupportUtils`

### Testing
Use `uv run pytest` to run tests after making changes.