from typing import Literal, Union
from pydantic import BaseModel


class StatusUpdateMessage(BaseModel):
    type: Literal["STATUS_UPDATE"]
    phase: str
    description: str


class LogMessage(BaseModel):
    type: Literal["LOG"]
    message: str
    icon: Literal["search", "read", "compare"]


class SourceFoundMessage(BaseModel):
    type: Literal["SOURCE_FOUND"]
    title: str
    url: str
    source_type: Literal["pdf", "web"]


class AwaitingInputMessage(BaseModel):
    type: Literal["AWAITING_INPUT"]
    question: str
    options: list[str]


class CompleteMessage(BaseModel):
    type: Literal["COMPLETE"]
    ui: str
    data: dict
    narrative: str


class UserChoiceMessage(BaseModel):
    type: Literal["USER_CHOICE"]
    choice: str


ServerMessage = Union[
    StatusUpdateMessage,
    LogMessage,
    SourceFoundMessage,
    AwaitingInputMessage,
    CompleteMessage,
]
