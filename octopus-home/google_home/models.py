"""Pydantic models for Google Home Cloud-to-Cloud fulfillment API."""
from typing import Any

from pydantic import BaseModel


class GoogleInput(BaseModel):
    intent: str
    payload: dict[str, Any] = {}


class GoogleRequest(BaseModel):
    requestId: str
    inputs: list[GoogleInput]
