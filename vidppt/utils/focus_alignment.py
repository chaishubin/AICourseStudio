"""Page-scoped focus alignment, independent of subtitle and audio segmentation.

Exact terminology and local sentence evidence outrank model annotations. Layout
links headings to explanations; a bounded sequence decoder resolves weak spans.
No page-wide bag of words or model-reported confidence is used as evidence.
"""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher

_SENTENCE_END = re.compile(r"[。！？!?；;]")
_OVERVIEW = re.compile(
    r"^(?:这[两二三四五几]种|以上|上述|总之|综上|总结一下|接下来.*(?:下一|另外)|下一[页节]|下面.*下一)"
)
_TRANSITION = re.compile(r"^(?:接下来|下一[页节]|我们将|我们马上|这就引出)")
_PARALLEL = re.compile(r"分为|分别|比较|相比|区别|两者|二者")
_TOPIC_SWITCH = re.compile(
    r"^(?:首先|其次|再次|最后|第[一二三四五六七八九十\d]+[种项步个]|接下来|再看|回到|回顾)"
)
_CONTINUATION = re.compile(
    r"^(?:它|其|这[个种一]|其中|因此|所以|也|既|特别|适合|例如|比如|由|从而|并且|同时|说明|可以|能够)"
)
_NO_FOCUS_DISCOURSE = re.compile(
    r"^(?:大家好|同学们好|欢迎(?:大家)?(?:来到|学习|参加)|感谢(?:大家)?(?:观看|收看|聆听)|"
    r"谢谢大家|本(?:页|节|课|章)(?:主要)?(?:介绍|讲解|学习|包括|涵盖)|"
    r"(?:下面|接下来)(?:我们)?(?:进入|开始学习|学习下一)|"
    r"(?:请|大家)(?:先)?(?:暂停|思考一下|想一想|思考这|独立思考)|"
    r"(?:不同|这些|上述|以上).*(?:根据|适合|各有|选择))"
)
_LOCAL_REFERENCE = re.compile(r"左侧|右侧|上方|下方|图中|表中|这个公式|该公式|这个步骤|第[一二三四五六七八九十\d]+[行列步]")


def no_focus_reason(text: str, context: str, cue: dict) -> str:
    """Decide whether a visual pointer is useful before scoring its location."""
    value, sentence = compact(text), compact(context)
    if cue.get("action") == "clear":
        return "explicit_clear"
    if _LOCAL_REFERENCE.search(sentence):
        return ""
    if _NO_FOCUS_DISCOURSE.match(sentence) or _NO_FOCUS_DISCOURSE.match(value):
        return "discourse_without_local_reference"
    if _OVERVIEW.match(value) or _OVERVIEW.match(sentence):
        return "overview_or_clear"
    return ""


def compact(value: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]+", "", str(value or "")).lower()


def similarity(left: str, right: str) -> float:
    a, b = compact(left), compact(right)
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b, autojunk=False).ratio()
    overlap = len(set(a) & set(b)) / max(1, len(set(a) | set(b)))
    # Short substrings such as “图” or “是” are not semantic evidence.
    containment = 0.25 if min(len(a), len(b)) >= 4 and (a in b or b in a) else 0
    score = ratio * 0.6 + overlap * 0.4 + containment
    longest = SequenceMatcher(None, a, b, autojunk=False).find_longest_match().size
    if longest >= 6:
        score = max(score, 0.45 + 0.35 * longest / min(len(a), len(b)))
    return min(1.0, score)


def target_aliases(target: dict) -> list[str]:
    text = str(target.get("text") or "").strip()
    aliases = [text]
    explicit = target.get("aliases") or []
    if isinstance(explicit, list):
        aliases.extend(str(item) for item in explicit if item)
    # “逻辑功能块图 (Function Block Diagram，FBD)” is one concept,
    # not a long bilingual sentence whose English dilutes a Chinese match.
    heading = re.split(r"[（(:：]", text, maxsplit=1)[0].strip()
    heading = re.sub(r"^(?:[一二三四五六七八九十\d]+[、.．]\s*)", "", heading)
    if 3 <= len(compact(heading)) <= 30:
        aliases.append(heading)
    for parenthesis in re.findall(r"[（(]([^）)]+)[）)]", text):
        aliases.extend(part.strip() for part in re.split(r"[,，/]", parenthesis))
    return list(dict.fromkeys(alias for alias in aliases if len(compact(alias)) >= 2))


def _visible(target: dict) -> bool:
    # Non-rendering callers may supply text-only targets. If any geometry is
    # present, require a complete finite box rather than silently accepting it.
    if not any(key in target for key in ("x", "y", "width", "height")):
        return True
    try:
        x, y, w, h = (float(target[key]) for key in ("x", "y", "width", "height"))
        return (
            all(math.isfinite(v) for v in (x, y, w, h))
            and min(x, y) >= 0
            and min(w, h) > 0
            and x + w <= 1.001
            and y + h <= 1.001
        )
    except (KeyError, TypeError, ValueError):
        return False


def page_target_index(targets: list[dict]) -> list[dict]:
    """Infer conservative heading/explanation groups without changing shape IDs."""
    indexed = []
    for target in targets:
        if not target.get("id") or not _visible(target):
            continue
        aliases = target_aliases(target)
        text = str(target.get("text") or "")
        head = re.split(r"[（(:：]", text, maxsplit=1)[0].strip()
        heading = (len(head) <= 24 and head != text) or (
            3 <= len(compact(text)) <= 16 and not re.search(r"[。！？；，,]", text)
        )
        indexed.append(
            {
                **target,
                "aliases": aliases,
                "heading": heading,
                "group": str(target.get("knowledge_point_id") or target["id"]),
            }
        )
    by_id = {str(t["id"]): t for t in indexed}
    for target in indexed:
        parent = by_id.get(str(target.get("parent_id") or ""))
        if parent:
            target["group"] = parent["group"]
        elif not target["heading"] and target.get("role") != "title" and "y" in target:
            headings = [
                h
                for h in indexed
                if h["heading"]
                and "y" in h
                and 0 <= float(target["y"]) - float(h["y"]) <= 0.25
                and abs(float(target.get("x", 0)) - float(h.get("x", 0))) < 0.2
            ]
            if headings:
                parent = min(headings, key=lambda h: float(target["y"]) - float(h["y"]))
                target["group"] = parent["group"]
    return indexed


def _mentions(text: str, target: dict) -> list[tuple[int, int]]:
    value = compact(text)
    found = []
    for alias in target["aliases"]:
        term = compact(alias)
        if len(term) < 3 and not (term.isascii() and term.isalpha() and len(term) >= 2):
            continue
        pos = value.find(term)
        # English abbreviations must match whole tokens, e.g. IL != similar.
        if term.isascii() and term.isalpha():
            match = re.search(
                r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", text, re.I
            )
            if not match:
                continue
        if pos >= 0:
            found.append((pos, len(term)))
    return found


def _score(text: str, target: dict) -> float:
    scores = []
    for alias in target["aliases"]:
        term = compact(alias)
        if term.isascii() and term.isalpha() and len(term) <= 4:
            if not re.search(
                r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", text, re.I
            ):
                continue
        scores.append(similarity(text, alias))
    return max(scores, default=0.0)


def _sentence_contexts(script: str, cues: list[dict]) -> list[str]:
    """Locate cues by source offsets; repeated sentences never use fuzzy search."""
    spans, start, offset = [], 0, 0
    for match in _SENTENCE_END.finditer(script):
        end = match.end()
        part = script[start:end]
        length = len(compact(part))
        spans.append((offset, offset + length, part))
        offset += length
        start = end
    if start < len(script):
        part = script[start:]
        spans.append((offset, offset + len(compact(part)), part))
    result, cursor = [], 0
    for cue in cues:
        length = len(compact(cue["text"]))
        # Use the sentence at the beginning of the cue, never the whole page.
        result.append(
            next((text for a, b, text in spans if a <= cursor < b), cue["text"])
        )
        cursor += length
    return result


def align_cues(
    script: str, cues: list[dict], targets: list[dict], *, suppress_automatic: bool = False
) -> tuple[list[dict], dict]:
    """Decode a page sequence with lexical anchors and a no-focus state.

    Scores describe deterministic evidence, not calibrated probabilities.
    Annotations can resolve paraphrases, but cannot override explicit concepts.
    Audio boundaries and subtitle text are carried through byte-for-byte.
    """
    indexed = page_target_index(targets)
    by_id = {str(t["id"]): t for t in indexed}
    contexts = _sentence_contexts(script, cues)
    emissions, reasons, fixed = [], [], []
    for cue, context in zip(cues, contexts):
        text = str(cue.get("text") or "")
        value = compact(text)
        scores = {str(t["id"]): _score(text, t) for t in indexed}
        why = {key: "local_text" for key in scores}
        chosen = str(cue.get("target_id") or "")
        manual = cue.get("manual") is True or cue.get("reviewed") is True
        suppression = no_focus_reason(text, context, cue)
        mentions = [
            (pos, -length, str(t["id"]))
            for t in indexed
            for pos, length in _mentions(text, t)
            if t["heading"]
        ]
        # Prefer the first explicitly named concept in a subtitle. A later
        # explanation may mention another term without switching its subject.
        mentions.sort()
        first_mentions = (
            {key for pos, size, key in mentions if (pos, size) == mentions[0][:2]}
            if mentions
            else set()
        )
        direct = next(iter(first_mentions)) if len(first_mentions) == 1 else ""
        if manual:
            scores = {chosen: 1.0} if chosen in by_id or not chosen else {"": 1.0}
            why = {key: "manual" for key in scores}
            fixed.append(True)
        elif (
            suppress_automatic or suppression
            or (
                _TRANSITION.match(value)
                and not direct
                and max(scores.values(), default=0) < 0.38
            )
        ):
            scores, why = {"": 1.0}, {"": "page_overview" if suppress_automatic else suppression or "overview_or_clear"}
            fixed.append(True)
        elif direct:
            detail = max(indexed, key=lambda t: scores[str(t["id"])])
            detail_id = str(detail["id"])
            if (
                not detail["heading"]
                and detail["group"] == by_id[direct]["group"]
                and scores[detail_id] >= 0.8
                and not _TOPIC_SWITCH.match(value)
            ):
                direct = detail_id
            scores, why = {direct: 0.96}, {direct: "explicit_term"}
            fixed.append(True)
        else:
            # Look ahead only inside the same sentence. This resolves an
            # introductory fragment ("首先，PLC最常用") split by subtitle width.
            context_heads = [
                (pos, -length, str(t["id"]))
                for t in indexed
                if t["heading"]
                for pos, length in _mentions(context, t)
            ]
            context_heads.sort()
            best = max(scores.values(), default=0)
            context_first = (
                {
                    key
                    for pos, size, key in context_heads
                    if (pos, size) == context_heads[0][:2]
                }
                if context_heads
                else set()
            )
            if best < 0.38 and len(context_first) == 1:
                group = context_heads[0][2]
                scores[group] = max(scores.get(group, 0), 0.63)
                why[group] = "sentence_concept"
                for target in indexed:
                    if (
                        target["group"] == by_id[group]["group"]
                        and str(target["id"]) != group
                    ):
                        key = str(target["id"])
                        scores[key] = max(scores.get(key, 0), 0.61)
                        why[key] = "sentence_concept"
            # Model annotations serve as bounded paraphrase evidence only.
            # An old planner decision is never treated as a fresh annotation.
            annotation = str(
                cue.get("model_target_id") or cue.get("anchor_id") or chosen
            )
            model_evidence = cue.get("model_target_id") or (
                cue.get("source") == "llm" and not cue.get("mapping_source")
            )
            if model_evidence and annotation in by_id and not context_heads:
                if best < 0.38 or scores.get(annotation, 0) >= best - 0.12:
                    scores[annotation] = max(scores.get(annotation, 0), 0.56)
                    why[annotation] = "model_annotation"
            if (
                best < 0.38
                and not context_heads
                and emissions
                and (cue.get("action") == "continue" or _CONTINUATION.match(value))
                and not _TOPIC_SWITCH.match(value)
            ):
                for key, prior in emissions[-1].items():
                    if key and prior >= 0.52:
                        scores[key] = max(scores.get(key, 0), 0.44)
                        why[key] = "local_continuation"
            scores = {key: score for key, score in scores.items() if score >= 0.34}
            # An almost tied pair is ambiguous; sequence evidence may resolve it.
            ranked = sorted(scores, key=scores.get, reverse=True)
            if len(ranked) > 1:
                first, second = ranked[:2]
                if (
                    scores[first] - scores[second] < 0.08
                    and by_id[first]["group"] != by_id[second]["group"]
                    and why[first] == why[second] == "local_text"
                ):
                    top_score = scores[first]
                    for key in scores:
                        if top_score - scores[key] < 0.08:
                            scores[key] = min(scores[key], 0.35)
            scores[""] = 0.38
            why[""] = "insufficient_evidence"
            fixed.append(False)
        emissions.append(scores)
        reasons.append(why)

    # Viterbi with soft continuity, not a hard reading-order restriction. Revisit
    # is valid; a topic switch/clear blocks inheritance. Unsupported states are
    # never created merely because a previous box was highlighted.
    layers = []
    for i, scores in enumerate(emissions):
        layer = {}
        for state, emission in scores.items():
            best = (emission, "")
            if layers:
                options = []
                for previous, (total, _) in layers[-1].items():
                    bonus = 0.0
                    if not fixed[i] and state and previous:
                        if state == previous:
                            bonus = 0.055
                        elif by_id[state]["group"] == by_id[previous]["group"]:
                            bonus = 0.025
                    options.append((total + emission + bonus, previous))
                best = max(options, key=lambda item: item[0])
            layer[state] = best
        layers.append(layer)
    states = []
    if layers:
        state = max(layers[-1], key=lambda key: layers[-1][key][0])
        for layer in reversed(layers):
            states.append(state)
            state = layer[state][1]
        states.reverse()

    output, anomalies = [], []
    accepted = repaired = intentional_clear = manual_count = focused = 0
    for index, (raw, state) in enumerate(zip(cues, states)):
        cue = dict(raw)
        old = str(cue.get("target_id") or "")
        for key in ("recheck", "fallback", "decision", "evidence", "target_ids"):
            cue.pop(key, None)
        reason = reasons[index].get(state, "local_text")
        confidence = (
            min(1.0, emissions[index][state])
            if state or reason != "insufficient_evidence"
            else 0.0
        )
        changed = old != state
        if changed and "original_target_id" not in cue:
            cue["original_target_id"] = old
        repaired += "original_target_id" in cue
        focused += bool(state)
        accepted += bool(state) and reason != "manual"
        manual_count += reason == "manual"
        intentional_clear += reason in {"overview_or_clear", "page_overview", "explicit_clear", "discourse_without_local_reference"}
        if not state and reason == "insufficient_evidence":
            anomalies.append(
                {
                    "cue_index": index,
                    "text": cue["text"],
                    "reason": "insufficient_evidence",
                    "resolution": "automatic_clear",
                }
            )
        if reason == "model_annotation":
            cue["model_target_id"] = state
        ids = [state] if state else []
        if (
            state
            and reason == "explicit_term"
            and _PARALLEL.search(compact(cue["text"]))
        ):
            named = sorted(
                (pos, -length, str(t["id"]))
                for t in indexed
                if t["heading"]
                for pos, length in _mentions(cue["text"], t)
            )
            unique = list(dict.fromkeys(key for _, _, key in named))
            if 1 < len(unique) <= 4:
                ids = unique
        cue.update(
            target_id=state,
            target_ids=ids,
            knowledge_point_id=by_id[state]["group"] if state else "",
            weight=max(1, len(compact(cue["text"]))),
            confidence=round(confidence, 3),
            confidence_kind="evidence_score",
            mapping_source="manual" if reason == "manual" else "automatic",
            decision="accepted" if state else "no_focus",
            evidence=[reason]
            + (["automatic_repair"] if "original_target_id" in cue else []),
        )
        output.append(cue)
    total = len(output)
    degraded = len(anomalies)
    return output, {
        "version": 2,
        "cue_count": total,
        "automatic_accept_count": accepted,
        "automatic_accept_rate": round(accepted / total, 4) if total else None,
        "focus_coverage_rate": round(focused / total, 4) if total else None,
        "focused_cue_count": focused,
        "manual_cue_count": manual_count,
        "automatic_repair_count": repaired,
        "intentional_clear_count": intentional_clear,
        "degraded_count": degraded,
        "degraded_rate": round(degraded / total, 4) if total else 0.0,
        "anomalies": anomalies,
        "manual_review_suggestions": [],
    }
