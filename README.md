# Private Assistant Ground Station

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)
[![python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)

Owner: stkr22

## Ground Station: Central Audio Processing Hub

Ground Station is an open-source central processing hub designed to handle audio processing for private assistant satellite systems. It receives audio from multiple satellite devices and provides speech-to-text (STT), text-to-speech (TTS), and MQTT communication services.

### Architecture

The system follows a hub-and-spoke architecture where satellites handle wake word detection and silence detection, while the ground station provides centralized processing:

**Ground Station (`app/main.py`):**
- FastAPI-based WebSocket server supporting multiple satellite connections
- Handles speech-to-text (STT) and text-to-speech (TTS) API calls
- Communicates with MQTT broker for assistant integration  
- Processes audio only after wake word detection by satellites
- Provides error feedback to satellites via audio beeps

**Satellite Communication Protocol:**
- WebSocket endpoint: `/satellite`
- Control signals: `START_COMMAND`, `END_COMMAND`, `CANCEL_COMMAND`
- Audio data: Binary WebSocket messages (16kHz 16-bit PCM)
- Error feedback: `error_beep` signal sent to satellites

### Key Features

- **Multi-Satellite Support**: Handles connections from multiple satellite devices simultaneously
- **Centralized Processing**: STT/TTS processing handled by ground station, not satellites
- **MQTT Integration**: Publishes requests and receives responses via MQTT
- **Audio Buffering**: Collects audio from satellites until END_COMMAND signal
- **Room-based Routing**: Supports multiple rooms with topic-based message routing
- **Error Handling**: Audio feedback system for processing failures

### Processing Flow

1. **Connection**: Satellite connects to ground station via WebSocket
2. **Configuration**: Satellite sends room and audio configuration
3. **Wake Word**: Satellite detects wake word and sends `START_COMMAND`
4. **Audio Collection**: Ground station buffers audio chunks from satellite
5. **Processing**: Satellite sends `END_COMMAND`, ground station processes audio via STT
6. **MQTT**: Ground station publishes text to MQTT and receives assistant response
7. **Response**: Ground station converts response to audio via TTS and sends to satellite

### Configuration

- Server configuration via YAML files with STT/TTS API endpoints and MQTT settings
- No wake word or VAD configuration needed (handled by satellites)
- Room-based topic routing for multi-room support
- Configurable audio buffer limits and processing timeouts

### Performance Characteristics

- **Low Latency**: No wake word processing overhead on ground station
- **Scalable**: Supports multiple concurrent satellite connections
- **Reliable**: Audio buffering prevents data loss during transmission
- **Efficient**: Centralized STT/TTS processing reduces satellite resource usage