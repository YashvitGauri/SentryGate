"""The gateway.

Passes an OpenAI-shaped request through the cache and screening, then to the
model, and writes one line about it to the request log. Week 3 is the
vulnerable baseline: cache_first checks the cache before screening, and the
lookup ignores the stored verdict.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.cache import SemanticCache, build_cache
from app.config import Settings, get_settings
from app.logging_mw import JsonlWriter, RequestLogMiddleware
from app.providers import Provider, ProviderError, build_provider, estimate_tokens
from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ErrorResponse,
    prompt_hash,
    user_prompt,
)
from app.screening import build_screener

STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.provider = build_provider(settings)
    app.state.screener, app.state.screening_info = build_screener(settings)
    app.state.cache, app.state.cache_info = build_cache(settings)
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
    cache_info = getattr(app.state, "cache_info", {"backend": "unknown"})
    try:
        cache_info = dict(cache_info)
        cache_info["size"] = app.state.cache.size()
    except Exception:
        pass
    return {
        "status": "ok",
        "uptime_s": round(time.time() - STARTED_AT, 1),
        "provider_mode": settings.provider_mode,
        "default_model": settings.default_model,
        "build_sha": settings.build_sha,
        "log_path": str(settings.log_path),
        "config": settings.as_log_dict(),
        "screening": getattr(app.state, "screening_info", {"mode": "unknown"}),
        "cache": cache_info,
    }


@app.post("/v1/cache/clear")
def cache_clear() -> dict:
    """Reset between experiments. Doing it by hand corrupts results."""
    cleared = app.state.cache.clear()
    app.state.cache_info["size"] = app.state.cache.size()
    return {"cleared": cleared}


def _serve_hit(payload: dict, similarity: float, matched_id: str) -> ChatCompletionResponse:
    return ChatCompletionResponse.build(
        text=payload["response"],
        model=payload.get("model", "unknown"),
        tokens_in=estimate_tokens(payload.get("prompt_text", "")),
        tokens_out=estimate_tokens(payload.get("response", "")),
    )


def _screen_prompt(request: Request, response: Response, prompt: str):
    """Run the classifier once. Returns the verdict, sets headers and log."""
    record = request.state.record
    with record.stage("screen"):
        verdict = request.app.state.screener.screen(prompt)
    record.screening_ran = True
    record.verdict = verdict.to_dict()
    response.headers["X-SentryGate-Screened"] = "true"
    response.headers["X-SentryGate-Verdict"] = "blocked" if verdict.is_injection else "clean"
    response.headers["X-SentryGate-Injection-Score"] = f"{verdict.injection_score:.3f}"
    return verdict


def _blocked_response(request: Request, verdict) -> JSONResponse:
    record = request.state.record
    record.block_reason = "prompt_injection"
    blocked = _error(
        403,
        f"Blocked by SentryGate screening (injection score {verdict.injection_score:.3f}).",
        "sentrygate_blocked",
        "prompt_injection",
    )
    blocked.headers["X-SentryGate-Screened"] = "true"
    blocked.headers["X-SentryGate-Verdict"] = "blocked"
    blocked.headers["X-SentryGate-Injection-Score"] = f"{verdict.injection_score:.3f}"
    blocked.headers["X-SentryGate-Cache"] = record.cache_outcome
    return blocked


def _lookup_cache(request: Request, prompt: str, prompt_hash_value: str, threshold: float):
    """Embed and search. Records outcome, similarity and timings on the log."""
    record = request.state.record
    cache: SemanticCache = request.app.state.cache
    with record.stage("embed"):
        vector = cache.embedder.embed(prompt)
    with record.stage("cache"):
        result = cache.lookup_with_vector(prompt_hash_value, vector)
    record.cache_outcome = "hit" if result.hit else "miss"
    record.cache_similarity = result.similarity
    record.cache_matched_id = result.matched_id
    record.cache_threshold = threshold
    return result, vector


# Sync on purpose. FastAPI runs a plain def in a worker thread, so blocking
# provider, classifier and embedding calls cannot stall the server.
@app.post("/v1/chat/completions", response_model=None)
def chat_completions(
    body: ChatCompletionRequest, request: Request, response: Response
) -> ChatCompletionResponse | JSONResponse:
    settings: Settings = app.state.settings
    provider: Provider = app.state.provider
    record = request.state.record

    if body.stream:
        raise StreamingNotSupported()

    model = body.model or settings.default_model
    prompt = user_prompt(body.messages)
    prompt_hash_value = prompt_hash(model, body.messages)

    record.model_requested = body.model
    record.prompt_hash = prompt_hash_value
    record.prompt_len = len(prompt)

    if settings.pipeline_order == "cache_first":
        result, _ = _lookup_cache(request, prompt, prompt_hash_value, settings.sim_threshold)
        if result.hit:
            # Vulnerable on purpose: served with screening_ran=False.
            hit_response = _serve_hit(result.payload or {}, result.similarity, result.matched_id or "")
            record.model_used = (result.payload or {}).get("model", model)
            record.provider_source = "cache"
            record.tokens_in = estimate_tokens(prompt)
            record.tokens_out = estimate_tokens((result.payload or {}).get("response", ""))
            record.cost_usd = 0.0
            response.headers["X-SentryGate-Provider"] = "cache"
            response.headers["X-SentryGate-Screened"] = "false"
            response.headers["X-SentryGate-Verdict"] = "unscreened"
            response.headers["X-SentryGate-Cache"] = "hit"
            response.headers["X-SentryGate-Similarity"] = f"{result.similarity:.3f}"
            return hit_response
        verdict = _screen_prompt(request, response, prompt)
        if verdict.is_injection:
            return _blocked_response(request, verdict)
        return _miss_then_store(request, response, body, model, prompt, prompt_hash_value, verdict)

    # screen_first: the comparison arm. Screening always runs, even on a hit.
    verdict = _screen_prompt(request, response, prompt)
    if verdict.is_injection:
        return _blocked_response(request, verdict)
    result, _ = _lookup_cache(request, prompt, prompt_hash_value, settings.sim_threshold)
    if result.hit:
        hit_response = _serve_hit(result.payload or {}, result.similarity, result.matched_id or "")
        record.model_used = (result.payload or {}).get("model", model)
        record.provider_source = "cache"
        record.tokens_in = estimate_tokens(prompt)
        record.tokens_out = estimate_tokens((result.payload or {}).get("response", ""))
        record.cost_usd = 0.0
        response.headers["X-SentryGate-Provider"] = "cache"
        response.headers["X-SentryGate-Cache"] = "hit"
        response.headers["X-SentryGate-Similarity"] = f"{result.similarity:.3f}"
        return hit_response
    return _miss_then_store(request, response, body, model, prompt, prompt_hash_value, verdict)


def _miss_then_store(request, response, body, model, prompt, prompt_hash_value, verdict):
    settings: Settings = request.app.state.settings
    provider: Provider = request.app.state.provider
    cache: SemanticCache = request.app.state.cache
    record = request.state.record
    with record.stage("provider"):
        result = provider.complete(body, model)
    record.model_used = result.model
    record.provider_source = result.source
    record.tokens_in = result.tokens_in
    record.tokens_out = result.tokens_out
    record.cost_usd = result.cost_usd
    with record.stage("cache_store"):
        cache.store(
            prompt=prompt,
            prompt_hash=prompt_hash_value,
            response=result.text,
            model=result.model,
            verdict=record.verdict,
        )
    response.headers["X-SentryGate-Provider"] = result.source
    response.headers["X-SentryGate-Cache"] = "miss"
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
