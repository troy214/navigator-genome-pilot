"""Secret / PII redaction before anything is logged or indexed.

Status: SCAFFOLD (Designed). Patterns are a starting set, not a verified DLP solution.
No real patient data should pass through this pilot at all — benchmarks use public cases.
"""
import re

_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S+"), r"\1=<REDACTED>"),
    (re.compile(r"sk-[A-Za-z0-9]{10,}"), "<REDACTED_KEY>"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<REDACTED_EMAIL>"),
]


def redact(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text
