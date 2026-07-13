"""Build narration-to-slide focus mappings for preview and video playback."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from pptx import Presentation

from .subtitle_rules import subtitle_chunks


FOCUS_CUES_VERSION = 3
_MIN_FOCUS_SIMILARITY = 0.22
_IGNORED_TEXT = {
    "AI COURSE STUDIO",
    "课程内容",
    "课程导入",
    "封面页",
    "内容页",
    "过渡页",
    "结束页",
}


def extract_presentation_focus_targets(presentation_path: Path) -> list[list[dict]]:
    """Extract visible text boxes as normalized focusable regions per slide."""
    presentation = Presentation(str(presentation_path))
    slide_width = max(1, int(presentation.slide_width))
    slide_height = max(1, int(presentation.slide_height))
    pages: list[list[dict]] = []
    for slide in presentation.slides:
        targets = []
        for shape_index, shape in enumerate(slide.shapes, 1):
            if not getattr(shape, "has_text_frame", False):
                continue
            text = " ".join(
                part.strip() for part in str(getattr(shape, "text", "")).splitlines()
                if part.strip()
            )
            if not _is_focusable_text(text):
                continue
            x = _clamp(shape.left / slide_width)
            y = _clamp(shape.top / slide_height)
            width = _clamp(shape.width / slide_width, minimum=0.01)
            height = _clamp(shape.height / slide_height, minimum=0.01)
            if x + width > 1:
                width = max(0.01, 1 - x)
            if y + height > 1:
                height = max(0.01, 1 - y)
            targets.append({
                "id": f"shape-{shape_index}",
                "text": text[:160],
                "x": round(x, 5),
                "y": round(y, 5),
                "width": round(width, 5),
                "height": round(height, 5),
                "role": "title" if y < 0.24 else "content",
            })
        pages.append(normalize_focus_targets(targets))
    return pages


def normalize_focus_targets(targets: list[dict]) -> list[dict]:
    """Remove layout labels and keep targets in visual reading order."""
    focusable = [
        target for target in targets
        if isinstance(target, dict) and _is_focusable_text(str(target.get("text", "")))
    ]
    return sorted(
        _deduplicate_targets(focusable),
        key=lambda target: (round(float(target.get("y", 0)), 2), float(target.get("x", 0))),
    )


def build_focus_cues(script: str, targets: list[dict]) -> list[dict]:
    """Match semantic narration chunks to slide targets with monotonic fallback."""
    units = _narration_units(script)
    if not units or not targets:
        return []
    content_targets = [target for target in targets if target.get("role") != "title"]
    candidates = content_targets or targets
    cues = []
    previous_index = 0
    for unit in units:
        scored = []
        for target_index, target in enumerate(candidates):
            if target_index < previous_index:
                continue
            score = _text_similarity(unit, str(target.get("text", "")))
            scored.append((score, target_index, target))
        score, target_index, target = max(scored, key=lambda item: item[0])
        target_id = ""
        if score >= _MIN_FOCUS_SIMILARITY:
            target_id = target["id"]
            previous_index = target_index
        cues.append({
            "text": unit,
            "target_id": target_id,
            "weight": max(1, len(_compact_text(unit))),
        })
    return cues


def normalize_focus_cues(raw_cues, script: str, targets: list[dict]) -> list[dict]:
    """Keep user target choices while refreshing cue text after script edits."""
    automatic = build_focus_cues(script, targets)
    if not isinstance(raw_cues, list) or not automatic:
        return automatic
    valid_ids = {str(target.get("id")) for target in targets} | {""}
    manual_cues = [
        cue for cue in raw_cues
        if isinstance(cue, dict) and cue.get("manual") is True
    ]
    for cue in automatic:
        matches = [
            (_text_similarity(cue["text"], str(raw.get("text", ""))), raw)
            for raw in manual_cues
            if str(raw.get("target_id") or "") in valid_ids
        ]
        if not matches:
            continue
        similarity, raw = max(matches, key=lambda item: item[0])
        if similarity >= 0.55:
            cue["target_id"] = str(raw.get("target_id") or "")
            cue["manual"] = True
    return automatic


def focus_timeline(cues: list[dict], duration: float) -> list[dict]:
    """Convert cue weights into page-local start/end timestamps."""
    valid = [cue for cue in cues if isinstance(cue, dict)]
    if not valid or duration <= 0:
        return []
    weights = [max(1, int(cue.get("weight") or len(str(cue.get("text", ""))))) for cue in valid]
    total_weight = sum(weights)
    cursor = 0.0
    timeline = []
    for index, (cue, weight) in enumerate(zip(valid, weights)):
        end = duration if index == len(valid) - 1 else cursor + duration * weight / total_weight
        timeline.append({**cue, "start": cursor, "end": end})
        cursor = end
    return timeline


def _is_focusable_text(text: str) -> bool:
    clean = text.strip()
    if not clean or clean.upper() in _IGNORED_TEXT:
        return False
    if len(clean) <= 3 and re.fullmatch(r"[\d\s./-]+", clean):
        return False
    return True


def _deduplicate_targets(targets: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for target in targets:
        key = (
            _compact_text(target["text"]),
            round(float(target.get("x", 0)), 2),
            round(float(target.get("y", 0)), 2),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(target)
    return result


def _text_similarity(left: str, right: str) -> float:
    left_compact = _compact_text(left)
    right_compact = _compact_text(right)
    if not left_compact or not right_compact:
        return 0.0
    ratio = SequenceMatcher(None, left_compact, right_compact).ratio()
    containment = 0.35 if left_compact in right_compact or right_compact in left_compact else 0.0
    left_chars, right_chars = set(left_compact), set(right_compact)
    overlap = len(left_chars & right_chars) / max(1, len(left_chars | right_chars))
    return ratio * 0.55 + overlap * 0.45 + containment


def _compact_text(value: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]+", "", str(value or "")).lower()


def _narration_units(text: str) -> list[str]:
    """Prefer sentence-level focus changes while retaining subtitle length limits."""
    sentences = [
        part.strip(" \t\r\n。！？!?；;")
        for part in re.split(r"(?<=[。！？!?；;])", str(text or ""))
        if part.strip(" \t\r\n。！？!?；;")
    ]
    units = []
    for sentence in sentences:
        chunks = subtitle_chunks(sentence)
        units.extend(chunks or [sentence])
    return units


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))
