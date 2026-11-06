"""字幕分段规则：优先语义停顿，再控制单行字幕字数。"""

from __future__ import annotations

import re
import unicodedata

from .speech_text import safe_speech_boundary

MAX_SUBTITLE_LINES = 1
MAX_CHARS_PER_LINE = 28
MAX_SUBTITLE_CHARS = MAX_SUBTITLE_LINES * MAX_CHARS_PER_LINE
MIN_CHARS_PER_CUE = 6

STRONG_BREAK_RE = re.compile(r"(?<=[。！？!?；;])")
MEDIUM_BREAK_RE = re.compile(r"(?<=[：:])")
SOFT_BREAK_RE = re.compile(r"(?<=[，,、])")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
CJK_OR_WORD_RE = re.compile(r"[\u3400-\u9fffA-Za-z0-9]")
ASCII_WORD_RE = re.compile(r"[A-Za-z0-9]+")
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
    """按字幕可读性拆分文本，返回单行字幕块。"""
    normalized = _semantic_subtitle_text(text)
    if not normalized:
        return []

    chunks: list[str] = []
    current = ""
    for phrase in _semantic_phrases(normalized):
        phrase = normalize_subtitle_text(phrase)
        if not phrase:
            continue
        candidate = _join_subtitle_parts(current, phrase)
        if _subtitle_len(candidate) <= MAX_SUBTITLE_CHARS:
            current = candidate
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


def subtitle_source_chunks(text: str) -> list[str]:
    """Use subtitle breaks while keeping the original punctuation for TTS."""
    chunks = subtitle_chunks(text)
    if len(chunks) <= 1:
        return [text.strip()] if text.strip() else []

    return restore_subtitle_source(text, chunks) or [text.strip()]


def restore_subtitle_source(text: str, chunks: list[str]) -> list[str]:
    """Restore original punctuation to aligned display cues before speech synthesis.

    Return no chunks when their visible text differs from the source, so callers
    can discard stale cue boundaries rather than synthesize altered text.
    """

    def visible(char: str) -> bool:
        return not char.isspace() and (
            char in "《》" or not unicodedata.category(char).startswith("P")
        )

    positions = [index for index, char in enumerate(text) if visible(char)]
    source_chars = ''.join(text[index] for index in positions)
    cue_chars = ''.join(char for chunk in chunks for char in chunk if visible(char))
    if source_chars != cue_chars:
        return []
    sizes = [sum(visible(char) for char in chunk) for chunk in chunks]
    if sum(sizes) != len(positions) or not all(sizes):
        return []

    start = count = 0
    result = []
    for size in sizes[:-1]:
        count += size
        end = safe_speech_boundary(text, positions[count], start)
        if end <= start or end >= len(text):
            return []
        result.append(text[start:end].strip())
        start = end
    result.append(text[start:].strip())
    return result


def wrap_subtitle(text: str) -> str:
    """把单条字幕整理为单行，便于 SRT 与烧录样式稳定显示。"""
    return normalize_subtitle_text(text)


def normalize_subtitle_text(text: str) -> str:
    """清理字幕展示文本：仅保留书名号，其他标点用空格断句。"""
    normalized = _display_subtitle_text(text)
    if not normalized:
        return ""
    return normalized


def _semantic_subtitle_text(text: str) -> str:
    """保留语义标点用于拆分，但不作为最终字幕展示文本。"""
    normalized = _compact_subtitle_text(text)
    if not normalized:
        return ""
    return _ensure_terminal_punctuation(normalized)


def _display_subtitle_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return ""
    normalized = _normalize_punctuation(normalized)
    normalized = _remove_repeated_punctuation(normalized)

    chars: list[str] = []
    for char in normalized:
        if char in "《》":
            chars.append(char)
            continue
        category = unicodedata.category(char)
        if category.startswith("P"):
            chars.append(" ")
        else:
            chars.append(char)
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def _compact_subtitle_text(text: str, *, trim_breaks: bool = True) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return ""
    normalized = _normalize_punctuation(normalized)
    normalized = _remove_repeated_punctuation(normalized)
    if trim_breaks:
        return normalized.strip(BREAK_PUNCTUATION)
    return normalized


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
    quote_stack: list[str] = []
    for index, char in enumerate(text):
        if char not in "\"'“”‘’":
            result.append(char)
            continue

        before = text[index - 1] if index > 0 else ""
        after = text[index + 1] if index + 1 < len(text) else ""
        if (
            char in "'‘’"
            and before.isascii()
            and before.isalnum()
            and after.isascii()
            and after.isalnum()
        ):
            result.append(char)
            continue

        if char in "”’" and not quote_stack:
            # A semantic subtitle fragment may start with a closing quote whose
            # opening quote was in the previous fragment. Keep it as a closing
            # mark instead of trying to pop an empty local stack.
            result.append(char)
            continue

        if char in "”’" or (
            char in "\"'"
            and quote_stack
            and _quote_kind(quote_stack[-1]) == _quote_kind(char)
        ):
            depth = len(quote_stack)
            quote_stack.pop()
            result.append("”" if depth % 2 == 1 else "’")
            continue

        quote_stack.append(char)
        result.append("“" if len(quote_stack) % 2 == 1 else "‘")
    return "".join(result)


def _quote_kind(char: str) -> str:
    return "double" if char in '"“”' else "single"


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
    phrase = normalize_subtitle_text(text)
    chunks: list[str] = []
    while _subtitle_len(phrase) > MAX_SUBTITLE_CHARS:
        split_at = _best_split_index(phrase, MAX_SUBTITLE_CHARS)
        chunks.append(phrase[:split_at].strip())
        phrase = phrase[split_at:].strip()
    if phrase:
        chunks.append(phrase)
    return chunks


def _best_split_index(text: str, limit: int) -> int:
    window = text[:limit]
    for marks in (" ", "的地得在和与及或并而"):
        candidates = [window.rfind(mark) + 1 for mark in marks]
        split_at = max(candidates)
        if split_at >= MIN_CHARS_PER_CUE:
            return split_at
    for word in ASCII_WORD_RE.finditer(text):
        if word.start() >= limit:
            break
        if word.start() < limit < word.end():
            return word.start() or word.end()
    return limit


def _rebalance_short_chunks(chunks: list[str]) -> list[str]:
    balanced: list[str] = []
    for chunk in chunks:
        if (
            balanced
            and _subtitle_len(chunk) < MIN_CHARS_PER_CUE
            and _subtitle_len(_join_subtitle_parts(balanced[-1], chunk))
            <= MAX_SUBTITLE_CHARS
        ):
            balanced[-1] = _join_subtitle_parts(balanced[-1], chunk)
        else:
            balanced.append(chunk)
    return balanced


def _subtitle_len(text: str) -> int:
    return len(re.sub(r"\s+", "", normalize_subtitle_text(text)))


def _join_subtitle_parts(left: str, right: str) -> str:
    left = str(left or "").strip()
    right = str(right or "").strip()
    if not left:
        return right
    if not right:
        return left
    return f"{left} {right}"
