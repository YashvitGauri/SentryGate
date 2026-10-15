"""Phase 3: pick the model for a question, and fall back if it fails.

    fixed       every question goes to the model the client asked for
                (or DEFAULT_MODEL). The Phase 2 behaviour.
    difficulty  easy questions go to a cheap model, hard ones to a strong
                one. Most traffic is easy, so most of it gets cheaper.

The difficulty score is a short list of plain rules, not a model. Every
rule that fired is written to the log, so a wrong route can be explained
by reading one line. A learned router could replace it later; the rest
of the gateway only sees route() and RouteDecision.

Routing only happens on a cache miss, after screening. A blocked question
never reaches a model, and a hit costs nothing either way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.config import Settings

# (name, weight, pattern). Matched on the lower-cased question.
# Any one kind of hard work (code, maths, reasoning, a long question) is
# enough on its own to reach the default ROUTER_HARD_SCORE of 0.4.
_RULES: list[tuple[str, float, re.Pattern]] = [
    ("code", 0.5, re.compile(
        r"```|\bdef |\bclass |\bfunction\b|\bsql\b|\bregex\b|\bstack trace\b|\bcompile|"
        r"\b(write|debug|fix|refactor|implement)\b.{0,40}\b(code|program|script|function|query|bug)")),
    ("maths", 0.5, re.compile(
        r"\b(prove|proof|derive|integral|derivative|equation|solve|theorem|probability|"
        r"complexity|optimi[sz]e)\b|\d+\s*[\^*/]\s*\d+")),
    ("reasoning", 0.4, re.compile(
        r"\b(step by step|compare|contrast|analy[sz]e|evaluate|trade-?offs?|pros and cons|"
        r"design|architecture|strategy|critique|essay|in detail)\b")),
]
_LONG_TOKENS = 150     # about 600 characters
_MEDIUM_TOKENS = 60


@dataclass(frozen=True)
class RouteDecision:
    model: str
    tier: str                      # fixed, cheap or strong
    score: float = 0.0
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_log(self) -> dict:
        return {"model": self.model, "tier": self.tier, "score": self.score, "reasons": list(self.reasons)}


def difficulty(prompt: str) -> tuple[float, tuple[str, ...]]:
    """A score from 0 (easy) to 1 (hard), and the rules that raised it."""
    text = prompt.lower()
    score = 0.0
    reasons: list[str] = []
    for name, weight, pattern in _RULES:
        if pattern.search(text):
            score += weight
            reasons.append(name)
    tokens = len(prompt) // 4
    if tokens > _LONG_TOKENS:
        score += 0.4
        reasons.append("long")
    elif tokens > _MEDIUM_TOKENS:
        score += 0.15
        reasons.append("medium_length")
    if prompt.count("?") >= 2 or len(re.findall(r"(?m)^\s*(\d+[.)]|[-*])\s", prompt)) >= 2:
        score += 0.2
        reasons.append("several_parts")
    return round(min(score, 1.0), 3), tuple(reasons)


def route(settings: Settings, requested_model: str | None, prompt: str) -> RouteDecision:
    if settings.router_mode == "fixed":
        return RouteDecision(model=requested_model or settings.default_model, tier="fixed")
    score, reasons = difficulty(prompt)
    if score >= settings.router_hard_score:
        return RouteDecision(settings.router_strong_model, "strong", score, reasons)
    return RouteDecision(settings.router_cheap_model, "cheap", score, reasons)
