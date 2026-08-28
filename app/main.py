"""The gateway.

Right now it does two things: pass an OpenAI-shaped request to the model, and
write one line about it to the request log. No safety check, no cache. Those
arrive in Week 2 and Week 3 and plug into the same route.

The response headers and the log line already say what did and did not happen
to a request. "screened: false" is honest today, and in Week 4 the same field
on a cache hit is the whole finding.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.logging_mw import JsonlWriter, RequestLogMiddleware
from app.providers import Provider, ProviderError, build_provider
from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ErrorResponse,
    prompt_hash,
    user_prompt,
)

STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.provider = build_provider(settings)
    app.state.log_writer = JsonlWriter(settings.log_path)
    yield
    app.state.provider.close()
    app.state.log_writer.close()


app = FastAPI(title="SentryGate", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestLogMiddleware)


def _error(status: int, message: str, type_: str, code: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorResponse.build(message, type_, code))


def _note_refusal(request: Request, reason: str) -> None:
    """Say in the log why a request did not get an answer."""
    record = getattr(request.state, "record", None)
    if record is not None:
        record.block_reason = reason


@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
    _note_refusal(request, exc.error_type)
    return _error(exc.status_code, str(exc), exc.error_type, exc.code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # OpenAI clients expect an error object, not FastAPI's default detail list.
    _note_refusal(request, "invalid_request")
    return _error(400, str(exc.errors()), "invalid_request_error", "bad_request")


@app.get("/healthz")
def healthz() -> dict:
    settings: Settings = app.state.settings
    return {
        "status": "ok",
        "uptime_s": round(time.time() - STARTED_AT, 1),
        "provider_mode": settings.provider_mode,
        "default_model": settings.default_model,
        "build_sha": settings.build_sha,
        "log_path": str(settings.log_path),
        "config": settings.as_log_dict(),
        # Filled in as each part lands.
        "screening": "not built yet (Week 2)",
        "cache": "not built yet (Week 3)",
    }


# Sync on purpose. FastAPI runs a plain def in a worker thread, so a blocking
# HTTP call now, and a blocking model call in Week 2, cannot stall the server.
@app.post("/v1/chat/completions")
def chat_completions(
    body: ChatCompletionRequest, request: Request, response: Response
) -> ChatCompletionResponse:
    settings: Settings = app.state.settings
    provider: Provider = app.state.provider
    record = request.state.record

    if body.stream:
        raise StreamingNotSupported()

    model = body.model or settings.default_model
    prompt = user_prompt(body.messages)

    record.model_requested = body.model
    record.prompt_hash = prompt_hash(model, body.messages)
    record.prompt_len = len(prompt)

    with record.stage("provider"):
        result = provider.complete(body, model)

    record.model_used = result.model
    record.provider_source = result.source
    record.tokens_in = result.tokens_in
    record.tokens_out = result.tokens_out
    record.cost_usd = result.cost_usd

    response.headers["X-SentryGate-Provider"] = result.source
    # Honest placeholders until the real parts exist.
    response.headers["X-SentryGate-Screened"] = "false"
    response.headers["X-SentryGate-Verdict"] = "unscreened"
    response.headers["X-SentryGate-Cache"] = record.cache_outcome

    return ChatCompletionResponse.build(
        text=result.text,
        model=result.model,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
    )


class StreamingNotSupported(ProviderError):
    status_code = 400
    error_type = "invalid_request_error"
    code = "stream_not_supported"

    def __init__(self) -> None:
        super().__init__(
            "SentryGate does not stream yet. Send stream=false. "
            "Streaming and caching interact, so it lands after the cache is real."
        )
