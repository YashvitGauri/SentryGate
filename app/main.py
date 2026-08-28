"""The gateway.

Right now it does one thing: take an OpenAI-shaped request, pass it to the
model, hand the reply back. No safety check, no cache. Those arrive in Week 2
and Week 3 and plug into the same route.

The response headers already say what did and did not happen to a request.
"screened: false" is honest today, and in Week 4 the same header on a cache
hit is the whole finding.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.providers import Provider, ProviderError, build_provider
from app.schemas import ChatCompletionRequest, ChatCompletionResponse, ErrorResponse

STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.provider = build_provider(settings)
    yield
    app.state.provider.close()


app = FastAPI(title="SentryGate", version="0.1.0", lifespan=lifespan)


def _error(status: int, message: str, type_: str, code: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=ErrorResponse.build(message, type_, code))


@app.exception_handler(ProviderError)
async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
    return _error(exc.status_code, str(exc), exc.error_type, exc.code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # OpenAI clients expect an error object, not FastAPI's default detail list.
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
        "config": settings.as_log_dict(),
        # Filled in as each part lands.
        "screening": "not built yet (Week 2)",
        "cache": "not built yet (Week 3)",
    }


# Sync on purpose. FastAPI runs a plain def in a worker thread, so a blocking
# HTTP call now, and a blocking model call in Week 2, cannot stall the server.
@app.post("/v1/chat/completions")
def chat_completions(body: ChatCompletionRequest, response: Response) -> ChatCompletionResponse:
    settings: Settings = app.state.settings
    provider: Provider = app.state.provider
    request_id = uuid.uuid4().hex

    if body.stream:
        raise StreamingNotSupported()

    model = body.model or settings.default_model
    started = time.perf_counter()
    result = provider.complete(body, model)
    total_ms = (time.perf_counter() - started) * 1000

    response.headers["X-SentryGate-Request-Id"] = request_id
    response.headers["X-SentryGate-Provider"] = result.source
    response.headers["X-SentryGate-Latency-Ms"] = f"{total_ms:.1f}"
    # Honest placeholders until the real parts exist.
    response.headers["X-SentryGate-Screened"] = "false"
    response.headers["X-SentryGate-Verdict"] = "unscreened"
    response.headers["X-SentryGate-Cache"] = "disabled"

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
