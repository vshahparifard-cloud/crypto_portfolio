from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Message(Schema):
    message: str


class ErrorEnvelope(Schema):
    code: str
    message: str
    details: dict[str, Any] = {}
