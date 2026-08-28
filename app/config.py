"""Settings for the SentryGate gateway.

Every setting comes from the environment and is read once. A running gateway
cannot change its own behaviour halfway through an experiment, and every
request we log carries a copy of the flags, so a log file always says which
build and which settings produced it.

The flags in "the experiment" block below are the whole point. The baseline
and the defended build are the same code with different values here.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PIPELINE_ORDERS = ("cache_first", "screen_first")
PROVIDER_MODES = ("mock", "replay", "live")
ROUTER_MODES = ("fixed", "difficulty")


class ConfigError(RuntimeError):
    """A setting is missing or makes no sense. Raised at startup, never later."""


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    raw = raw.strip().lower()
    if raw in ("on", "true", "1", "yes"):
        return True
    if raw in ("off", "false", "0", "no"):
        return False
    raise ConfigError(f"{name} must be on or off, got {raw!r}")


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None


def _one_of(name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = _str(name, default)
    if value not in allowed:
        raise ConfigError(f"{name} must be one of {', '.join(allowed)}, got {value!r}")
    return value


def _build_sha() -> str:
    """Short commit the gateway is running. Goes on every log line."""
    from_env = os.environ.get("SENTRYGATE_BUILD_SHA")
    if from_env:
        return from_env.strip()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=2, check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


@dataclass(frozen=True)
class Settings:
    # --- the experiment ---------------------------------------------------
    # cache_first is what real products do, and it is the hole we are proving.
    pipeline_order: str
    # off = the vulnerable baseline of Phase 2. on = the Phase 3 defence.
    cache_verdict_filter: bool
    cache_reverify_high_risk: bool
    router_mode: str
    sim_threshold: float

    # --- provider ---------------------------------------------------------
    provider_mode: str
    provider_record: bool
    default_model: str
    openai_api_key: str
    openai_base_url: str
    request_timeout_s: float
    max_output_tokens: int
    spend_cap_usd_per_day: float

    # --- infrastructure ---------------------------------------------------
    qdrant_url: str
    redis_url: str
    log_path: Path
    cassette_dir: Path
    spend_ledger_path: Path

    build_sha: str = field(default_factory=_build_sha)

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(_str("SENTRYGATE_DATA_DIR", str(REPO_ROOT / "data")))
        settings = cls(
            pipeline_order=_one_of("PIPELINE_ORDER", "cache_first", PIPELINE_ORDERS),
            cache_verdict_filter=_bool("CACHE_VERDICT_FILTER", False),
            cache_reverify_high_risk=_bool("CACHE_REVERIFY_HIGH_RISK", False),
            router_mode=_one_of("ROUTER_MODE", "fixed", ROUTER_MODES),
            sim_threshold=_float("SIM_THRESHOLD", 0.85),
            provider_mode=_one_of("PROVIDER_MODE", "mock", PROVIDER_MODES),
            provider_record=_bool("PROVIDER_RECORD", False),
            default_model=_str("DEFAULT_MODEL", "gpt-4o-mini"),
            openai_api_key=_str("OPENAI_API_KEY", ""),
            openai_base_url=_str("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            request_timeout_s=_float("REQUEST_TIMEOUT_S", 60.0),
            max_output_tokens=int(_float("MAX_OUTPUT_TOKENS", 512)),
            spend_cap_usd_per_day=_float("SPEND_CAP_USD_PER_DAY", 2.0),
            qdrant_url=_str("QDRANT_URL", "http://qdrant:6333"),
            redis_url=_str("REDIS_URL", "redis://redis:6379/0"),
            log_path=data_dir / _str("LOG_FILE", "requests.jsonl"),
            cassette_dir=data_dir / "cassettes",
            spend_ledger_path=data_dir / "spend_ledger.json",
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not 0.0 < self.sim_threshold <= 1.0:
            raise ConfigError(f"SIM_THRESHOLD must be between 0 and 1, got {self.sim_threshold}")
        if self.spend_cap_usd_per_day <= 0:
            raise ConfigError("SPEND_CAP_USD_PER_DAY must be greater than 0")
        if self.provider_mode == "live" and not self.openai_api_key:
            raise ConfigError("PROVIDER_MODE=live needs OPENAI_API_KEY. Use mock or replay without a key.")
        if self.provider_record and self.provider_mode != "live":
            raise ConfigError("PROVIDER_RECORD only makes sense with PROVIDER_MODE=live")

    def as_log_dict(self) -> dict:
        """The config block that goes on every request log line.

        Anything that changes what an experiment measures belongs here, so a
        log file can be split by arm later without anyone remembering how it
        was run.
        """
        return {
            "pipeline_order": self.pipeline_order,
            "verdict_filter": "on" if self.cache_verdict_filter else "off",
            "reverify": "on" if self.cache_reverify_high_risk else "off",
            "router": self.router_mode,
            "sim_threshold": self.sim_threshold,
            "provider_mode": self.provider_mode,
            "build_sha": self.build_sha,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
