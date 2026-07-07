"""字幕分段规则：优先语义停顿，再控制每屏行数与字数。"""

from __future__ import annotations

import re

MAX_SUBTITLE_LINES = 2
MAX_CHARS_PER_LINE = 14
MAX_SUBTITLE_CHARS = MAX_SUBTITLE_LINES * MAX_CHARS_PER_LINE
MIN_CHARS_PER_CUE = 6

STRONG_BREAK_RE = re.compile(r"(?<=[。！？!?；;])")
MEDIUM_BREAK_RE = re.compile(r"(?<=[：:])")
SOFT_BREAK_RE = re.compile(r"(?<=[，,、])")
CONNECTORS = (
    "并且", "同时", "因此", "所以", "但是", "而且", "以及", "然后",
    "例如", "比如", "其中", "对于", "通过", "围绕", "基于",
)


def subtitle_chunks(text: str) -> list[str]:
    """按字幕可读性拆分文本，返回每屏最多两行的字幕块。"""
    normalized = _normalize_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    current = ""
    for phrase in _semantic_phrases(normalized):
        if not phrase:
            continue
        if _subtitle_len(current + phrase) <= MAX_SUBTITLE_CHARS:
            current += phrase
            continue
        if current:
            chunks.append(current)
            current = ""
        split_phrases = _split_long_phrase(phrase)
        if not split_phrases:
            continue
        chunks.extend(split_phrases[:-1])
        current = split_phrases[-1]

    if current:
        chunks.append(current)
    return _rebalance_short_chunks(chunks)


def wrap_subtitle(text: str) -> str:
    """把单条字幕整理为最多两行，便于 SRT 与烧录样式稳定显示。"""
    text = _normalize_text(text)
    if not text:
        return ""
    if _subtitle_len(text) <= MAX_CHARS_PER_LINE:
        return text
    first_end = _best_split_index(text, MAX_CHARS_PER_LINE)
    first = text[:first_end]
    second = text[first_end:first_end + MAX_CHARS_PER_LINE]
    return f"{first}\n{second}" if second else first


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "")).strip()


def _semantic_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    for strong in _split_keep_break(text, STRONG_BREAK_RE):
        if _subtitle_len(strong) <= MAX_SUBTITLE_CHARS:
            phrases.append(strong)
            continue
        for medium in _split_keep_break(strong, MEDIUM_BREAK_RE):
            if _subtitle_len(medium) <= MAX_SUBTITLE_CHARS:
                phrases.append(medium)
                continue
            for soft in _split_keep_break(medium, SOFT_BREAK_RE):
                if _subtitle_len(soft) <= MAX_SUBTITLE_CHARS:
                    phrases.append(soft)
                    continue
                phrases.extend(_split_after_connectors(soft))
    return [phrase for phrase in phrases if phrase]


def _split_keep_break(text: str, pattern: re.Pattern[str]) -> list[str]:
    return [part for part in pattern.split(text) if part]


def _split_after_connectors(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    index = 0
    while index < len(text):
        matched = next(
            (connector for connector in CONNECTORS if text.startswith(connector, index)),
            None,
        )
        if matched:
            end = index + len(matched)
            parts.append(text[start:end])
            start = end
            index = end
            continue
        index += 1
    if start < len(text):
        parts.append(text[start:])
    return [part for part in parts if part]


def _split_long_phrase(text: str) -> list[str]:
    phrase = _normalize_text(text)
    chunks: list[str] = []
    while _subtitle_len(phrase) > MAX_SUBTITLE_CHARS:
        split_at = _best_split_index(phrase, MAX_SUBTITLE_CHARS)
        chunks.append(phrase[:split_at])
        phrase = phrase[split_at:]
    if phrase:
        chunks.append(phrase)
    return chunks


def _best_split_index(text: str, limit: int) -> int:
    window = text[:limit]
    for marks in ("，,、：:", "的地得在和与及或并而"):
        candidates = [window.rfind(mark) + 1 for mark in marks]
        split_at = max(candidates)
        if split_at >= MIN_CHARS_PER_CUE:
            return split_at
    return limit


def _rebalance_short_chunks(chunks: list[str]) -> list[str]:
    balanced: list[str] = []
    for chunk in chunks:
        if (
            balanced
            and _subtitle_len(chunk) < MIN_CHARS_PER_CUE
            and _subtitle_len(balanced[-1] + chunk) <= MAX_SUBTITLE_CHARS
        ):
            balanced[-1] += chunk
        else:
            balanced.append(chunk)
    return balanced


def _subtitle_len(text: str) -> int:
    return len(_normalize_text(text))
