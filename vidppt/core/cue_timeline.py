"""Canonical narration timeline shared by subtitles, focus and interactions."""

from __future__ import annotations

import json
from pathlib import Path


CUE_TIMELINE_VERSION = 1


def build_cue_timeline(pages: list[dict]) -> dict:
    """Build a course-global timeline from page-local narration cues."""
    course_cursor = 0.0
    timeline_cues = []
    for page in pages:
        page_number = int(page["page_number"])
        slide_id = str(page.get("slide_id") or f"slide-{page_number}")
        duration = max(0.0, float(page.get("duration") or 0))
        cues = _page_local_cues(
            page.get("cues"), str(page.get("script") or ""), duration
        )
        for index, cue in enumerate(cues, 1):
            local_start = max(0.0, float(cue["start"]))
            local_end = min(duration, float(cue["end"]))
            if local_end <= local_start:
                continue
            target_ids = cue.get("target_ids")
            if not isinstance(target_ids, list):
                target_id = str(cue.get("target_id") or "").strip()
                target_ids = [target_id] if target_id else []
            timeline_cues.append({
                "cue_id": str(cue.get("cue_id") or f"cue-{page_number:03d}-{index:02d}"),
                "page_number": page_number,
                "slide_id": slide_id,
                "text": str(cue.get("text") or "").strip(),
                "start": round(course_cursor + local_start, 3),
                "end": round(course_cursor + local_end, 3),
                "page_start": round(local_start, 3),
                "page_end": round(local_end, 3),
                "target_ids": [str(item) for item in target_ids if str(item)],
                "mapping_source": str(
                    cue.get("mapping_source") or cue.get("source") or "fallback"
                ),
                "timing_source": str(
                    cue.get("timing_source") or "estimated_weight"
                ),
                "confidence": round(float(cue.get("confidence") or 0), 3),
                "reviewed": bool(cue.get("reviewed") or cue.get("manual")),
            })
        course_cursor += duration
    return {
        "version": CUE_TIMELINE_VERSION,
        "time_unit": "seconds",
        "duration": round(course_cursor, 3),
        "cues": timeline_cues,
    }


def page_cues_from_timeline(timeline: dict, page_number: int) -> list[dict]:
    """Return the page-local compatibility view consumed by focus playback."""
    result = []
    for cue in timeline.get("cues", []):
        if int(cue.get("page_number", 0)) != int(page_number):
            continue
        target_ids = list(cue.get("target_ids") or [])
        result.append({
            **cue,
            "start": float(cue["page_start"]),
            "end": float(cue["page_end"]),
            "target_id": target_ids[0] if target_ids else "",
        })
    return result


def slice_cue_timeline(
    timeline: dict, start_page: int, end_page: int
) -> dict:
    """Create a zero-based timeline for a lesson segment page range."""
    selected = [
        dict(cue) for cue in timeline.get("cues", [])
        if start_page <= int(cue.get("page_number", 0)) <= end_page
    ]
    if not selected:
        return {**timeline, "duration": 0.0, "cues": []}
    offset = min(float(cue["start"]) - float(cue["page_start"]) for cue in selected)
    for cue in selected:
        cue["start"] = round(float(cue["start"]) - offset, 3)
        cue["end"] = round(float(cue["end"]) - offset, 3)
    duration = max(float(cue["end"]) for cue in selected)
    return {**timeline, "duration": round(duration, 3), "cues": selected}


def shift_cue_timeline(
    timeline: dict,
    *,
    intro_seconds: float = 0.0,
    segment_durations: list[float] | None = None,
    mid_seconds: float = 0.0,
    outro_seconds: float = 0.0,
) -> dict:
    """Align content cues with intro/mid/outro clips in a packaged video."""
    intro = max(0.0, float(intro_seconds))
    mid = max(0.0, float(mid_seconds))
    outro = max(0.0, float(outro_seconds))
    durations = [max(0.0, float(item)) for item in segment_durations or []]
    boundaries = []
    cursor = 0.0
    for duration in durations[:-1]:
        cursor += duration
        boundaries.append(cursor)
    shifted = []
    for cue in timeline.get("cues", []):
        original_start = float(cue.get("start", 0))
        original_end = float(cue.get("end", original_start))
        inserted_before = sum(
            mid for boundary in boundaries if original_start >= boundary - 0.001
        )
        shifted.append({
            **cue,
            "content_start": original_start,
            "content_end": original_end,
            "start": round(original_start + intro + inserted_before, 3),
            "end": round(original_end + intro + inserted_before, 3),
        })
    total_mid = mid * len(boundaries)
    return {
        **timeline,
        "duration": round(
            float(timeline.get("duration") or 0) + intro + total_mid + outro,
            3,
        ),
        "packaging": {
            "intro_seconds": intro,
            "mid_seconds": mid,
            "mid_count": len(boundaries),
            "outro_seconds": outro,
        },
        "cues": shifted,
    }


def write_cue_timeline(timeline: dict, output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def _page_local_cues(raw_cues, script: str, duration: float) -> list[dict]:
    cues = [
        dict(cue) for cue in raw_cues or []
        if isinstance(cue, dict) and str(cue.get("text") or "").strip()
    ]
    if not cues:
        return [{
            "text": script,
            "start": 0.0,
            "end": duration,
            "target_ids": [],
            "timing_source": "page_audio",
        }]
    timed = []
    for cue in cues:
        try:
            start = float(cue.get("start"))
            end = float(cue.get("end"))
        except (TypeError, ValueError):
            timed = []
            break
        if end <= start:
            timed = []
            break
        timed.append({**cue, "start": start, "end": end})
    if len(timed) == len(cues):
        return timed

    weights = [max(1, int(cue.get("weight") or len(cue["text"]))) for cue in cues]
    total = sum(weights)
    cursor = 0.0
    result = []
    for index, (cue, weight) in enumerate(zip(cues, weights)):
        end = duration if index == len(cues) - 1 else cursor + duration * weight / total
        result.append({
            **cue,
            "start": cursor,
            "end": end,
            "timing_source": "estimated_weight",
        })
        cursor = end
    return result
