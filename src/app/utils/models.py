"""Pydantic models for API requests and responses."""

from pydantic import BaseModel


class TextMessageRequest(BaseModel):
    """Request model for PUT /text endpoint.

    Attributes:
        text: The transcribed text from the device
        device_id: Unique identifier for the device sending the request
    """

    text: str
    device_id: str


class TextMessageResponse(BaseModel):
    """Response model for PUT /text endpoint.

    Attributes:
        status: Status of the request (e.g., 'accepted')
        request_id: Unique identifier for tracking the request
    """

    status: str
    request_id: str
