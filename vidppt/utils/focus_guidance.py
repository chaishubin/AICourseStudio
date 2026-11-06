"""Build narration-to-slide focus mappings for preview and video playback."""

from __future__ import annotations

import re
import math
from difflib import SequenceMatcher
from pathlib import Path


from .subtitle_rules import subtitle_chunks
from .focus_alignment import align_cues


FOCUS_CUES_VERSION = 10
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
    """Extract native text, chart, table, image and formula regions per slide."""
    from ..processors.slide_objects import presentation_objects
    return [normalize_focus_targets(objects) for objects in presentation_objects(presentation_path)]


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
    if annotated and _compact_text("".join(cue["text"] for cue in annotated)) == _compact_text(script):
        return annotated
    cues = [{"text": unit, "source": "fallback"} for unit in units]
    return align_cues(script, cues, targets)[0]


def plan_page_focus(
    script: str,
    targets: list[dict],
    annotated_cues: list[dict] | None = None,
    *,
    page_context: str = "",
    page_kind: str = "",
    previous_target_id: str = "",
) -> tuple[list[dict], dict]:
    """Plan a page using local concepts and a shared subtitle/audio timeline.

    Compatibility context arguments are intentionally not lexical evidence:
    a page title may contain the beginning of its script, and target IDs from
    other pages must never leak into this page's decisions.
    """
    # Fresh structured LLM output has anchor_id/target_text and no source
    # marker yet. Resolve it before normalizing saved subtitle/audio cues.
    if isinstance(annotated_cues, list) and any(
        isinstance(cue, dict)
        and any(key in cue for key in ("anchor_id", "target_text", "target", "action"))
        and not any(cue.get(key) for key in ("source", "mapping_source", "subtitle_unit", "manual"))
        for cue in annotated_cues
    ):
        annotated_cues = build_focus_cues(script, targets, annotated_cues)
    cues = normalize_focus_cues(annotated_cues, script, targets)
    if not cues and str(script or "").strip():
        cues = [{"text": unit, "source": "fallback"} for unit in _narration_units(script)]
    # Page titles only suppress overview pages; they never supply match evidence.
    overview_page = page_kind in {"cover", "section", "summary", "ending"} or bool(re.fullmatch(
        r"(?:封面|课程导入|课程概览|目录|章节过渡|结束(?:语|页)?|谢谢(?:大家|观看)?|感谢观看|本课小结|课程总结)",
        str(page_context or "").strip(),
    ))
    return align_cues(script, cues, targets, suppress_automatic=overview_page)


def validate_focus_events(events: list[dict], targets: list[dict], duration: float) -> list[dict]:
    """Validate event timing, target references, and normalized geometry."""
    valid_ids = {str(item.get("id")) for item in targets}
    output = []
    previous_end = 0.0
    for event in events:
        try:
            start, end = float(event.get("start", 0)), float(event.get("end", 0))
        except (TypeError, ValueError):
            continue
        ids = [str(item) for item in event.get("target_ids", [])]
        if not math.isfinite(start) or not math.isfinite(end) or start < previous_end or end <= start or end > duration + 0.02 or not set(ids) <= valid_ids:
            continue
        safe_ids = [item for item in ids if _target_is_visible(next(t for t in targets if str(t.get("id")) == item))]
        output.append({**event, "target_ids": safe_ids})
        previous_end = end
    return output


def _target_is_visible(target: dict) -> bool:
    try:
        x, y = float(target.get("x", 0)), float(target.get("y", 0))
        width, height = float(target.get("width", 0)), float(target.get("height", 0))
        return width > 0 and height > 0 and x >= 0 and y >= 0 and x + width <= 1.001 and y + height <= 1.001
    except (TypeError, ValueError):
        return False


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
            item = {
                "text": text, "target_id": "", "anchor_id": "",
                "weight": max(1, len(_compact_text(text))),
                "source": "llm", "confidence": 1.0,
            }
            _copy_focus_intent(item, raw)
            resolved.append(item)
            continue
        if action == "continue" and not target_id:
            target_id = previous_id
        if action == "continue" and not target_id:
            item = {
                "text": text, "target_id": "", "anchor_id": "",
                "weight": max(1, len(_compact_text(text))),
                "source": "llm", "confidence": 1.0,
            }
            _copy_focus_intent(item, raw)
            resolved.append(item)
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
        item = {
            "text": text,
            "target_id": target_id,
            "anchor_id": annotated_anchor_id,
            "weight": max(1, len(_compact_text(text))),
            "source": "llm",
            "confidence": round(min(1.0, confidence), 3),
        }
        _copy_focus_intent(item, raw)
        resolved.append(item)
    return resolved


def _copy_focus_intent(destination: dict, raw: dict) -> None:
    action = str(raw.get("action") or "").strip().lower()
    stage = str(raw.get("teaching_stage") or raw.get("stage") or "").strip()
    point_id = str(raw.get("knowledge_point_id") or "").strip()
    if action:
        destination["action"] = action
    if stage:
        destination["teaching_stage"] = stage
    if point_id:
        destination["knowledge_point_id"] = point_id


def normalize_focus_cues(raw_cues, script: str, targets: list[dict]) -> list[dict]:
    """Keep user target choices while refreshing cue text after script edits."""
    if not isinstance(raw_cues, list) or not str(script or "").strip():
        return build_focus_cues(script, targets)
    valid_ids = {str(target.get("id")) for target in targets} | {""}
    persistent_cues = [
        cue for cue in raw_cues
        if isinstance(cue, dict)
        and (
            cue.get("manual") is True
            or cue.get("source") == "llm"
            or cue.get("subtitle_unit") is True
        )
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
                "target_id": str(cue.get("target_id") or "") if str(cue.get("target_id") or "") in valid_ids else "",
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
    automatic = build_focus_cues(script, targets)
    for cue in automatic:
        matches = [
            (_text_similarity(cue["text"], str(raw.get("text", ""))), raw)
            for raw in persistent_cues if raw.get("manual") is True
        ]
        if not matches:
            continue
        similarity, raw = max(matches, key=lambda item: item[0])
        if similarity >= 0.55:
            cue["target_id"] = str(raw.get("target_id") or "")
            if raw.get("manual") is True:
                cue["manual"] = True
                if raw.get("focus_mode") in {"off", "target"}:
                    cue["focus_mode"] = raw["focus_mode"]
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


def rebuild_focus_events(cues: list[dict], existing: list[dict] | None = None) -> list[dict] | None:
    """Rebuild automatic events from real cue times, overlaying manual intervals.

    Never invent new timestamps when migrating an old page. An explicit empty
    manual interval is meaningful and must mask the generated highlight.
    """
    from vidppt.core.cue_timeline import focus_events_from_cues

    # Cue choices follow regenerated speech timestamps, not their old seconds.
    # Independently calibrated intervals retain their explicit time boundaries.
    manual = [dict(event) for event in existing or []
              if (event.get('manual') or event.get('reviewed'))
              and event.get('binding') != 'cue']
    timed = []
    previous = 0.0
    for cue in cues:
        try:
            start, end = float(cue['start']), float(cue['end'])
        except (KeyError, TypeError, ValueError):
            return manual or None
        if not math.isfinite(start) or not math.isfinite(end) or start < previous or end <= start:
            return manual or None
        timed.append({**cue, 'start': start, 'end': end})
        previous = end
    automatic = focus_events_from_cues(timed)
    for event in automatic:
        if event.get('manual') or event.get('reviewed'):
            event['binding'] = 'cue'
    if not manual:
        return automatic if timed else None
    # Subtract manually controlled spans from the automatic track. Preserve
    # manual metadata exactly; edited/stale intervals are handled by the caller.
    result = list(manual)
    for event in automatic:
        spans = [(event['start'], event['end'])]
        for override in manual:
            a, b = float(override['start']), float(override['end'])
            spans = [(left, right) for start, end in spans
                     for left, right in ((start, min(end, a)), (max(start, b), end))
                     if right > left]
        result.extend({**event, 'start': start, 'end': end} for start, end in spans)
    return sorted(result, key=lambda event: (float(event['start']), float(event['end'])))
