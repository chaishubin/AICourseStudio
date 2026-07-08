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
CJK_RE = re.compile(r"[\u3400-\u9fff]")
CJK_OR_WORD_RE = re.compile(r"[\u3400-\u9fffA-Za-z0-9]")
ENDING_PUNCTUATION = "。！？；……"
BREAK_PUNCTUATION = "，、；："
CONNECTORS = (
    "并且",
    "同时",
    "因此",
    "所以",
    "但是",
    "而且",
    "以及",
    "然后",
    "例如",
    "比如",
    "其中",
    "对于",
    "通过",
    "围绕",
    "基于",
)


def subtitle_chunks(text: str) -> list[str]:
    """按字幕可读性拆分文本，返回每屏最多两行的字幕块。"""
    normalized = normalize_subtitle_text(text)
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
    text = _compact_subtitle_text(text)
    if not text:
        return ""
    if _subtitle_len(text) <= MAX_CHARS_PER_LINE:
        return text
    first_end = _best_split_index(text, MAX_CHARS_PER_LINE)
    first = text[:first_end]
    second = text[first_end : first_end + MAX_CHARS_PER_LINE]
    return f"{first}\n{second}" if second else first


def normalize_subtitle_text(text: str) -> str:
    """按中文课程字幕的展示场景规范化标点，并补齐整段句末点号。"""
    normalized = _compact_subtitle_text(text)
    if not normalized:
        return ""
    return _ensure_terminal_punctuation(normalized)


def _compact_subtitle_text(text: str) -> str:
    normalized = re.sub(r"\s+", "", str(text or "")).strip()
    if not normalized:
        return ""
    normalized = _normalize_punctuation(normalized)
    normalized = _remove_repeated_punctuation(normalized)
    return normalized.strip(BREAK_PUNCTUATION)


def _normalize_punctuation(text: str) -> str:
    has_cjk = bool(CJK_RE.search(text))
    if not has_cjk:
        return text

    text = re.sub(r"\.{3,}", "……", text)
    text = re.sub(r"…{2,}", "……", text)
    text = re.sub(r"(?<![A-Za-z0-9])[-—]{2,}(?![A-Za-z0-9])", "——", text)
    text = text.translate(
        str.maketrans(
            {
                "?": "？",
                "!": "！",
                ";": "；",
                ":": "：",
                "(": "（",
                ")": "）",
                "[": "【",
                "]": "】",
            }
        )
    )
    text = _normalize_quotes(text)
    text = _normalize_periods(text)
    text = _normalize_commas(text)
    return text


def _normalize_quotes(text: str) -> str:
    result: list[str] = []
    opening = True
    for char in text:
        if char != '"':
            result.append(char)
            continue
        result.append("“" if opening else "”")
        opening = not opening
    return "".join(result)


def _normalize_periods(text: str) -> str:
    chars = list(text)
    for index, char in enumerate(chars):
        if char != ".":
            continue
        before = chars[index - 1] if index > 0 else ""
        after = chars[index + 1] if index + 1 < len(chars) else ""
        if before.isdigit() and after.isdigit():
            continue
        chars[index] = "。"
    return "".join(chars)


def _normalize_commas(text: str) -> str:
    chars = list(text)
    for index, char in enumerate(chars):
        if char != ",":
            continue
        before = chars[index - 1] if index > 0 else ""
        after = chars[index + 1] if index + 1 < len(chars) else ""
        if before.isdigit() and after.isdigit():
            continue
        if (
            before.isascii()
            and before.isalnum()
            and after.isascii()
            and after.isalnum()
        ):
            chars[index] = "、"
        else:
            chars[index] = "，"
    return "".join(chars)


def _remove_repeated_punctuation(text: str) -> str:
    text = re.sub(r"([。！？；：，、])\1+", r"\1", text)
    text = re.sub(r"([。！？；：，、])([。！？；：，、])+", r"\1", text)
    return text


def _ensure_terminal_punctuation(text: str) -> str:
    tail = text.rstrip("”’）】》")
    if not tail:
        return text
    if tail.endswith(tuple(ENDING_PUNCTUATION)):
        return text
    if CJK_OR_WORD_RE.search(tail[-1]):
        return f"{text}。"
    return text


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
            (
                connector
                for connector in CONNECTORS
                if text.startswith(connector, index)
            ),
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
    phrase = _compact_subtitle_text(text)
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
    return len(_compact_subtitle_text(text))
