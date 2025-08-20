from pydantic import BaseModel


class ClientConfig(BaseModel):
    samplerate: int
    input_channels: int
    output_channels: int
    chunk_size: int
    room: str
    output_topic: str = ""
