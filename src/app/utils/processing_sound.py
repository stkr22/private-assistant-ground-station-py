import logging
import math
import uuid
from dataclasses import dataclass
from enum import Enum

import numpy as np
from fastapi import WebSocket
from private_assistant_commons import messages

from app.utils import (
    client_config,
    config,
    support_utils,
)
from app.utils import (
    speech_recognition_tools as srt,
)


class ProcessingState(Enum):
    IDLE = "idle"
    COLLECTING_AUDIO = "collecting_audio"
    PROCESSING_STT = "processing_stt"


@dataclass
class AudioConfig:
    max_frames: int
    max_buffer_size: int = 1024 * 1024  # 1MB max buffer size


class SatelliteAudioProcessor:
    """Processes audio from satellites in the new ground station architecture."""

    def __init__(
        self,
        websocket: WebSocket,
        config_obj: config.Config,
        client_conf: client_config.ClientConfig,
        logger: logging.Logger,
        sup_util: support_utils.SupportUtils,
    ) -> None:
        self.websocket = websocket
        self.config_obj = config_obj
        self.client_conf = client_conf
        self.logger = logger
        self.sup_util = sup_util

        self.audio_config = AudioConfig(
            max_frames=config_obj.max_command_input_seconds * client_conf.samplerate,
        )

        # Audio processing state
        self.state = ProcessingState.IDLE
        self.audio_buffer: list[bytes] = []
        self._buffer_size_bytes: int = 0

    async def handle_control_signal(self, signal: str) -> None:
        """Handle control signals from satellite."""
        self.logger.debug("Received control signal: %s", signal)

        if signal == "START_COMMAND":
            await self._start_audio_collection()
        elif signal == "END_COMMAND":
            await self._end_audio_collection()
        elif signal == "CANCEL_COMMAND":
            await self._cancel_processing()
        else:
            self.logger.warning("Unknown control signal: %s", signal)

    async def handle_audio_data(self, audio_bytes: bytes) -> None:
        """Handle audio data from satellite."""
        if self.state != ProcessingState.COLLECTING_AUDIO:
            self.logger.warning("Received audio data while not collecting audio, ignoring")
            return

        # Check buffer size limits
        if self._buffer_size_bytes + len(audio_bytes) > self.audio_config.max_buffer_size:
            self.logger.warning("Audio buffer size limit reached, processing current audio")
            await self._process_collected_audio()
            return

        # Add to buffer
        self.audio_buffer.append(audio_bytes)
        self._buffer_size_bytes += len(audio_bytes)

        self.logger.debug("Collected audio chunk (buffer size: %d bytes)", self._buffer_size_bytes)

        # Check if we've exceeded the maximum audio duration
        total_samples = sum(len(chunk) // 2 for chunk in self.audio_buffer)  # 16-bit audio = 2 bytes per sample
        if total_samples > self.audio_config.max_frames:
            self.logger.info("Maximum audio duration reached, processing current audio")
            await self._process_collected_audio()

    async def _start_audio_collection(self) -> None:
        """Start collecting audio from satellite."""
        if self.state != ProcessingState.IDLE:
            self.logger.warning("Cannot start audio collection, processor not idle")
            return

        self.state = ProcessingState.COLLECTING_AUDIO
        self.audio_buffer.clear()
        self._buffer_size_bytes = 0
        self.logger.info("Started collecting audio from satellite")

    async def _end_audio_collection(self) -> None:
        """End audio collection and process the collected audio."""
        if self.state != ProcessingState.COLLECTING_AUDIO:
            self.logger.warning("Cannot end audio collection, not currently collecting")
            return

        await self._process_collected_audio()

    async def _cancel_processing(self) -> None:
        """Cancel current audio processing."""
        self.logger.info("Cancelling audio processing")
        self.state = ProcessingState.IDLE
        self.audio_buffer.clear()
        self._buffer_size_bytes = 0

    async def _process_collected_audio(self) -> None:
        """Process the collected audio buffer."""
        if not self.audio_buffer:
            self.logger.warning("No audio data to process")
            self.state = ProcessingState.IDLE
            return

        self.state = ProcessingState.PROCESSING_STT

        try:
            # Concatenate all audio chunks
            full_audio_bytes = b"".join(self.audio_buffer)
            audio_array = np.frombuffer(full_audio_bytes, dtype=np.int16)

            self.logger.info("Processing %d bytes of audio (%d samples)", len(full_audio_bytes), len(audio_array))

            # Convert to float32 for STT API
            audio_float = srt.int2float(audio_array)

            # Send to STT API
            response = await srt.send_audio_to_stt_api(audio_float, config_obj=self.config_obj)

            if response is None:
                self.logger.error("Failed to get STT response")
                await self._send_error_feedback()
                return

            self.logger.info("STT result: %s", response.text)

            # Send to MQTT
            request = messages.ClientRequest(
                id=uuid.uuid4(),
                text=response.text,
                room=self.client_conf.room,
                output_topic=self.client_conf.output_topic,
            )

            await self.sup_util.mqtt_client.publish(
                self.config_obj.input_topic,
                request.model_dump_json(),
                qos=1,
            )
            self.logger.info("Published STT result to MQTT")

        except Exception as e:
            self.logger.error("Error processing audio: %s", e)
            await self._send_error_feedback()
        finally:
            # Reset state
            self.state = ProcessingState.IDLE
            self.audio_buffer.clear()
            self._buffer_size_bytes = 0

    def _generate_error_beep(self, duration: float = 0.5, frequency: int = 800) -> bytes:
        """Generate error beep audio data."""
        sample_rate = self.client_conf.samplerate
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples, False)

        # Generate beep with fade in/out to avoid clicks
        beep = np.sin(2 * math.pi * frequency * t)
        fade_samples = int(sample_rate * 0.05)  # 50ms fade

        if fade_samples > 0:
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            beep[:fade_samples] *= fade_in
            beep[-fade_samples:] *= fade_out

        # Convert to 16-bit PCM
        beep_int16 = (beep * 32767).astype(np.int16)
        return bytes(beep_int16.tobytes())

    async def _send_error_feedback(self) -> None:
        """Send error feedback to satellite."""
        try:
            # Generate and send error beep
            error_beep_audio = self._generate_error_beep()
            await self.websocket.send_bytes(error_beep_audio)
            self.logger.debug("Sent error beep to satellite")
        except Exception as e:
            self.logger.error("Failed to send error feedback: %s", e)
