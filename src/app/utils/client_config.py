"""Client configuration models for satellite connections."""

from pydantic import BaseModel


class ClientConfig(BaseModel):
    """Configuration for satellite client connections."""

    samplerate: int
    input_channels: int
    output_channels: int
    chunk_size: int
    room: str
    output_topic: str = ""
