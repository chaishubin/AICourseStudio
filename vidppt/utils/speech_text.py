"""Boundaries for speech requests must keep numbers and technical terms intact."""

import re


SPEECH_TOKEN_RE = re.compile(
    r"\$[A-Za-z0-9_?@#!*$-]+|"
    r"[+\-−]?[A-Za-z0-9]+(?:[._’':/,+\-]+[A-Za-z0-9]+)*"
    r"(?:[%％℃]|°[CF]|[+#]+)?"
)


def safe_speech_boundary(text: str, end: int, start: int = 0) -> int:
    """Move a cut before a token, or after it if it starts the current chunk."""
    for token in SPEECH_TOKEN_RE.finditer(text, start):
        if token.start() >= end:
            break
        if token.start() < end < token.end():
            return token.start() if token.start() > start else token.end()
    return end
