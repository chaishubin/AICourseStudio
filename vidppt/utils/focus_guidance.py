"""Build narration-to-slide focus mappings for preview and video playback."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

from pptx import Presentation

from .subtitle_rules import subtitle_chunks


FOCUS_CUES_VERSION = 6
_QUOTED_ENGLISH = re.compile(r"""[‘“'"]([A-Za-z]+(?: +[A-Za-z]+)+)[’”'"]""")
_MIN_VISIBLE_FOCUS_CONFIDENCE = 0.34
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
    for slide_number, slide in enumerate(presentation.slides, 1):
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
            anchor_id = f"p{slide_number}-a{shape_index}"
            targets.append({
                "id": anchor_id,
                "anchor_id": anchor_id,
                "shape_id": f"shape-{shape_index}",
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


def build_focus_cues(
    script: str,
    targets: list[dict],
    annotated_cues: list[dict] | None = None,
) -> list[dict]:
    """Resolve AI annotations first, then deterministically match remaining narration."""
    units = _narration_units(script)
    if not units or not targets:
        return []
    annotated = _resolve_annotated_cues(annotated_cues, targets)
    if annotated:
        return annotated
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
        target_id = target["id"] if score >= _MIN_VISIBLE_FOCUS_CONFIDENCE else ""
        if target_id:
            previous_index = target_index
        cues.append({
            "text": unit,
            "target_id": target_id,
            "weight": max(1, len(_compact_text(unit))),
            "confidence": round(min(1.0, score), 3),
            "source": "fallback",
        })
    return cues


def _resolve_annotated_cues(raw_cues, targets: list[dict]) -> list[dict]:
    """Turn LLM target text/id annotations into stable PPT shape ids."""
    if not isinstance(raw_cues, list):
        return []
    targets_by_id = {str(target.get("id")): target for target in targets}
    resolved = []
    previous_id = ""
    for raw in raw_cues:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        action = str(raw.get("action") or "").strip().lower()
        target_id = str(
            raw.get("anchor_id") or raw.get("target_id") or ""
        ).strip()
        if action == "clear":
            previous_id = ""
            resolved.append({
                "text": text, "target_id": "", "anchor_id": "",
                "weight": max(1, len(_compact_text(text))),
                "source": "llm", "confidence": 1.0,
            })
            continue
        if action == "continue" and not target_id:
            target_id = previous_id
        if action == "continue" and not target_id:
            resolved.append({
                "text": text, "target_id": "", "anchor_id": "",
                "weight": max(1, len(_compact_text(text))),
                "source": "llm", "confidence": 1.0,
            })
            continue
        annotated_anchor_id = target_id
        target = targets_by_id.get(target_id)
        confidence = 0.98 if target is not None else 0.0
        if target is not None:
            chosen_score = _text_similarity(text, str(target.get("text", "")))
            best_score = max(
                _text_similarity(text, str(item.get("text", "")))
                for item in targets
            )
            if best_score >= 0.45 and best_score - chosen_score >= 0.2:
                target_id = ""
                confidence = 0.25
        if target is None:
            target_text = str(
                raw.get("target_text") or raw.get("target") or ""
            ).strip()
            if not target_text:
                continue
            target = max(
                targets,
                key=lambda item: _text_similarity(
                    target_text, str(item.get("text", ""))
                ),
            )
            target_id = str(target.get("id") or "")
            confidence = _text_similarity(
                target_text, str(target.get("text", ""))
            )
            annotated_anchor_id = target_id
            if confidence < _MIN_VISIBLE_FOCUS_CONFIDENCE:
                target_id = ""
        if not annotated_anchor_id:
            continue
        previous_id = target_id
        resolved.append({
            "text": text,
            "target_id": target_id,
            "anchor_id": annotated_anchor_id,
            "weight": max(1, len(_compact_text(text))),
            "source": "llm",
            "confidence": round(min(1.0, confidence), 3),
        })
    return resolved


def normalize_focus_cues(raw_cues, script: str, targets: list[dict]) -> list[dict]:
    """Keep user target choices while refreshing cue text after script edits."""
    automatic = build_focus_cues(script, targets)
    if not isinstance(raw_cues, list) or not str(script or "").strip():
        return automatic
    valid_ids = {str(target.get("id")) for target in targets} | {""}
    persistent_cues = [
        cue for cue in raw_cues
        if isinstance(cue, dict)
        and (
            cue.get("manual") is True
            or cue.get("source") == "llm"
            or cue.get("subtitle_unit") is True
        )
        and str(cue.get("target_id") or "") in valid_ids
    ]
    if (
        persistent_cues
        and _compact_text(
            "".join(str(cue.get("text", "")) for cue in persistent_cues)
        )
        == _compact_text(script)
    ):
        return [
            {
                **cue,
                "target_id": str(cue.get("target_id") or ""),
                "weight": max(
                    1,
                    int(
                        cue.get("weight")
                        or len(_compact_text(cue.get("text", "")))
                    ),
                ),
            }
            for cue in persistent_cues
        ]
    for cue in automatic:
        matches = [
            (_text_similarity(cue["text"], str(raw.get("text", ""))), raw)
            for raw in persistent_cues
        ]
        if not matches:
            continue
        similarity, raw = max(matches, key=lambda item: item[0])
        if similarity >= 0.55:
            cue["target_id"] = str(raw.get("target_id") or "")
            if raw.get("manual") is True:
                cue["manual"] = True
            if raw.get("source") == "llm":
                cue["source"] = "llm"
    return automatic


def focus_timeline(cues: list[dict], duration: float) -> list[dict]:
    """Convert cue weights into page-local start/end timestamps."""
    valid = [cue for cue in cues if isinstance(cue, dict)]
    if not valid or duration <= 0:
        return []
    timed = []
    for cue in valid:
        try:
            start = max(0.0, float(cue.get("start")))
            end = min(duration, float(cue.get("end")))
        except (TypeError, ValueError):
            timed = []
            break
        if end <= start:
            timed = []
            break
        timed.append({**cue, "start": start, "end": end})
    if len(timed) == len(valid):
        return timed
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
        # Keep quoted English phrases intact for speech synthesis.
        for index, part in enumerate(_QUOTED_ENGLISH.split(sentence)):
            if index % 2:
                units.append(part)
            else:
                units.extend(subtitle_chunks(part))
    return units


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))
