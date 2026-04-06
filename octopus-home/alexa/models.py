"""Pydantic models for Alexa Smart Home Skill API v3 directives and responses."""
from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Inbound directive structure
# ---------------------------------------------------------------------------

class AlexaEndpoint(BaseModel):
    endpointId: str
    cookie: dict[str, str] = {}


class AlexaDirectiveHeader(BaseModel):
    namespace: str
    name: str
    payloadVersion: str = "3"
    messageId: str
    correlationToken: str | None = None


class AlexaDirective(BaseModel):
    header: AlexaDirectiveHeader
    endpoint: AlexaEndpoint | None = None
    payload: dict[str, Any] = {}


class AlexaRequest(BaseModel):
    directive: AlexaDirective


# ---------------------------------------------------------------------------
# Outbound response helpers (built as plain dicts for flexibility)
# ---------------------------------------------------------------------------

def make_response_header(
    name: str,
    namespace: str = "Alexa",
    correlation_token: str | None = None,
    message_id: str | None = None,
) -> dict:
    import uuid
    h = {
        "namespace": namespace,
        "name": name,
        "payloadVersion": "3",
        "messageId": message_id or str(uuid.uuid4()),
    }
    if correlation_token:
        h["correlationToken"] = correlation_token
    return h


def make_power_state_property(state: bool) -> dict:
    from datetime import datetime, timezone
    return {
        "namespace": "Alexa.PowerController",
        "name": "powerState",
        "value": "ON" if state else "OFF",
        "timeOfSample": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.00Z"),
        "uncertaintyInMilliseconds": 500,
    }
