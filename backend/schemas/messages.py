"""
The WebSocket message protocol — the contract between FastAPI and Next.js.

Every event published to a session channel is validated against these models,
so the backend cannot silently drift from what the frontend expects.
"""
import logging
from typing import Literal, Union, Optional, Any

from pydantic import BaseModel, ValidationError

log = logging.getLogger("aletheia.protocol")

LogIcon = Literal["search", "read", "compare", "list", "check"]


class StatusUpdateMessage(BaseModel):
    type: Literal["STATUS_UPDATE"]
    phase: str
    description: str


class LogMessage(BaseModel):
    type: Literal["LOG"]
    message: str
    icon: LogIcon = "search"


class SourceFoundMessage(BaseModel):
    type: Literal["SOURCE_FOUND"]
    title: str
    url: str
    snippet: str = ""
    source_type: Literal["pdf", "web"] = "web"
    published_year: Optional[int] = None


class SourcesSyncMessage(BaseModel):
    """Authoritative source list, sent after a decision prunes sources."""
    type: Literal["SOURCES_SYNC"]
    sources: list[dict]


class AwaitingInputMessage(BaseModel):
    type: Literal["AWAITING_INPUT"]
    question: str
    options: list[str]
    gate_id: str = ""


class CompleteMessage(BaseModel):
    type: Literal["COMPLETE"]
    ui: str
    data: dict
    narrative: str


class ErrorMessage(BaseModel):
    type: Literal["ERROR"]
    message: str
    recoverable: bool = False


ServerMessage = Union[
    StatusUpdateMessage,
    LogMessage,
    SourceFoundMessage,
    SourcesSyncMessage,
    AwaitingInputMessage,
    CompleteMessage,
    ErrorMessage,
]

_BY_TYPE: dict[str, type[BaseModel]] = {
    "STATUS_UPDATE": StatusUpdateMessage,
    "LOG": LogMessage,
    "SOURCE_FOUND": SourceFoundMessage,
    "SOURCES_SYNC": SourcesSyncMessage,
    "AWAITING_INPUT": AwaitingInputMessage,
    "COMPLETE": CompleteMessage,
    "ERROR": ErrorMessage,
}


def validate_event(event: dict[str, Any]) -> dict[str, Any]:
    """
    Validate an outgoing event against the protocol.

    Logs and passes the event through on mismatch rather than raising — a
    protocol slip should surface loudly in the logs, not kill a live mission.
    """
    model = _BY_TYPE.get(event.get("type", ""))
    if model is None:
        log.warning("Unknown event type %r — not in the protocol.", event.get("type"))
        return event
    try:
        return model.model_validate(event).model_dump(mode="json")
    except ValidationError as e:
        log.warning("Event failed protocol validation (%s): %s", event.get("type"), e)
        return event


# Client -> server
class StartMissionMessage(BaseModel):
    type: Literal["START_MISSION"]
    query: str


class UserResponseMessage(BaseModel):
    type: Literal["USER_RESPONSE"]
    choice: str
