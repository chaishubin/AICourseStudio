"""Build narration-to-slide focus mappings for preview and video playback."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from pptx import Presentation

from .subtitle_rules import subtitle_chunks


_IGNORED_TEXT = {"AI COURSE STUDIO", "课程内容", "课程导入"}


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
        pages.append(_deduplicate_targets(targets))
    return pages


def build_focus_cues(script: str, targets: list[dict]) -> list[dict]:
    """Match semantic narration chunks to slide targets with monotonic fallback."""
    units = _narration_units(script)
    if not units or not targets:
        return []
    content_targets = [target for target in targets if target.get("role") != "title"]
    candidates = content_targets or targets
    cues = []
    previous_index = 0
    for unit_index, unit in enumerate(units):
        scored = []
        for target_index, target in enumerate(candidates):
            score = _text_similarity(unit, str(target.get("text", "")))
            if target_index < previous_index:
                score -= 0.12
            scored.append((score, target_index, target))
        score, target_index, target = max(scored, key=lambda item: item[0])
        if score < 0.18:
            target_index = min(
                len(candidates) - 1,
                round(unit_index * len(candidates) / max(1, len(units))),
            )
            target = candidates[target_index]
        previous_index = max(previous_index, target_index)
        cues.append({
            "text": unit,
            "target_id": target["id"],
            "weight": max(1, len(_compact_text(unit))),
        })
    return cues


def normalize_focus_cues(raw_cues, script: str, targets: list[dict]) -> list[dict]:
    """Keep user target choices while refreshing cue text after script edits."""
    automatic = build_focus_cues(script, targets)
    if not isinstance(raw_cues, list) or not automatic:
        return automatic
    valid_ids = {str(target.get("id")) for target in targets}
    for index, cue in enumerate(automatic):
        if index >= len(raw_cues) or not isinstance(raw_cues[index], dict):
            continue
        target_id = str(raw_cues[index].get("target_id") or "")
        if target_id in valid_ids:
            cue["target_id"] = target_id
    return automatic


def focus_timeline(cues: list[dict], duration: float) -> list[dict]:
    """Convert cue weights into page-local start/end timestamps."""
    valid = [cue for cue in cues if cue.get("target_id")]
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
            round(target["x"], 2),
            round(target["y"], 2),
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
