"""Request and reply shapes.

We speak the same JSON as OpenAI's /v1/chat/completions. That way any OpenAI
client points at SentryGate by changing one base URL, and the load test in
Phase 4 needs no special code.

Our own numbers (cache hit, verdict, similarity) ride in response headers, not
in the body, so the body stays a valid OpenAI reply.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    # Unknown OpenAI fields are kept rather than rejected, so a normal client
    # library does not break on us.
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    user: str | None = None


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage

    @classmethod
    def build(cls, text: str, model: str, tokens_in: int, tokens_out: int) -> "ChatCompletionResponse":
        return cls(
            id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
            created=int(time.time()),
            model=model,
            choices=[Choice(message=ChatMessage(role="assistant", content=text))],
            usage=Usage(
                prompt_tokens=tokens_in,
                completion_tokens=tokens_out,
                total_tokens=tokens_in + tokens_out,
            ),
        )


class ErrorBody(BaseModel):
    message: str
    type: str
    code: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody

    @classmethod
    def build(cls, message: str, type_: str, code: str | None = None) -> dict[str, Any]:
        return cls(error=ErrorBody(message=message, type=type_, code=code)).model_dump()


def user_prompt(messages: list[ChatMessage]) -> str:
    """The text we screen, embed and cache on.

    It is the last thing the user actually said. System messages are ours or
    the app's, and earlier turns are context, so neither one is what an attack
    variant changes.
    """
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return messages[-1].content


def prompt_hash(model: str, messages: list[ChatMessage]) -> str:
    """Exact-match key. Same model and same conversation means same answer."""
    parts = [model] + [f"{m.role}:{m.content}" for m in messages]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
