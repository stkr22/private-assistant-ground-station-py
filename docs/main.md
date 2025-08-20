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

### Ground Station Config (YAML)

```yaml
speech_transcription_api: "http://localhost:8000/transcribe"
speech_transcription_api_token: null
speech_synthesis_api: "http://localhost:8080/synthesizeSpeech" 
speech_synthesis_api_token: null
client_id: "ground-station-01"
max_command_input_seconds: 30
mqtt_server_host: "localhost"
mqtt_server_port: 1883
broadcast_topic: "assistant/ground_station/broadcast"
base_topic_overwrite: null
input_topic_overwrite: null  
output_topic_overwrite: null
error_audio_path: "/app/assets/error_beep.wav"
```

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
- Broadcast: `assistant/ground_station/broadcast`

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