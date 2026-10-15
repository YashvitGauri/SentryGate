"""Phase 3: look at the answer before it leaves the gateway.

The input filter judges the question. This judges the reply, including a
reply served from the cache, which is exactly the one the input filter never
saw in the Phase 2 attack. It looks for the few things an answer should
almost never carry to an app that trusts it:

    script   HTML/JS that runs in a browser (stored XSS through the cache)
    sql      statements that destroy or dump data
    shell    commands that delete files or pipe the internet into a shell
    secret   strings shaped like API keys or private keys

Modes (OUTPUT_GUARD):

    off     do nothing (default, the Phase 2 behaviour)
    flag    serve the answer, but say what was found in a header and the log
    block   refuse the answer, and never save a refused answer to the cache

These are plain patterns. They catch the obvious payloads, not a clever
attacker; the paper reports what they catch and what they miss.
"""

from __future__ import annotations

import re

PATTERNS: dict[str, re.Pattern] = {
    "script": re.compile(r"<\s*script\b|javascript\s*:|\bon(error|load)\s*=", re.I),
    "sql": re.compile(r"\b(drop\s+(table|database)|truncate\s+table|union\s+(all\s+)?select)\b"
                      r"|\bdelete\s+from\s+\w+\s*;", re.I),
    "shell": re.compile(r"\brm\s+-[a-z]*r[a-z]*f|\b(curl|wget)\b[^\n|]*\|\s*(ba|z)?sh\b"
                        r"|\bchmod\s+777\b|/etc/(passwd|shadow)\b|\bmkfs\b", re.I),
    "secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{30,}"
                         r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def scan(text: str) -> list[str]:
    """Names of the patterns found in the text, in a fixed order."""
    return [name for name, pattern in PATTERNS.items() if pattern.search(text or "")]
