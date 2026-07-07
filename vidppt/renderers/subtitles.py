"""根据逐页讲稿与音频时长生成基础 SRT 字幕。"""

import re
from pathlib import Path

from ..core.course import CourseSection

# 高校课程常见验收口径：每屏一行，控制在 20 个汉字以内。
MAX_SUBTITLE_CHARS = 20


class SubtitleRenderer:
    def render_page(self, page: CourseSection, duration: float, output_path: Path) -> Path:
        sentences = _subtitle_chunks(page.script)
        if not sentences:
            sentences = [page.script.strip() or page.title]

        weights = [max(1, len(sentence)) for sentence in sentences]
        total_weight = sum(weights)
        cursor = 0.0
        entries = []
        for index, (sentence, weight) in enumerate(zip(sentences, weights), 1):
            end = duration if index == len(sentences) else cursor + duration * weight / total_weight
            entries.append(
                f"{index}\n{_srt_time(cursor)} --> {_srt_time(end)}\n"
                f"{_wrap_subtitle(sentence)}\n"
            )
            cursor = end

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(entries), encoding="utf-8")
        return output_path

    def render_course(
        self,
        pages: list[tuple[CourseSection, float]],
        output_path: Path,
    ) -> Path:
        """生成覆盖整门课程时间轴的 SRT。"""
        cursor = 0.0
        index = 1
        entries = []
        for page, duration in pages:
            sentences = _subtitle_chunks(page.script) or [
                page.script.strip() or page.title
            ]
            weights = [max(1, len(sentence)) for sentence in sentences]
            total_weight = sum(weights)
            page_cursor = cursor
            for sentence_index, (sentence, weight) in enumerate(
                zip(sentences, weights), 1
            ):
                end = (
                    cursor + duration
                    if sentence_index == len(sentences)
                    else page_cursor + duration * weight / total_weight
                )
                entries.append(
                    f"{index}\n{_srt_time(page_cursor)} --> {_srt_time(end)}\n"
                    f"{_wrap_subtitle(sentence)}\n"
                )
                page_cursor = end
                index += 1
            cursor += duration

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(entries), encoding="utf-8")
        return output_path


def _subtitle_chunks(text: str) -> list[str]:
    """按语义标点切成适合画面展示的短字幕，避免长讲稿覆盖幻灯片。"""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    phrases = [
        item.strip()
        for item in re.split(r"(?<=[。！？!?；;，,：:])", text)
        if item.strip()
    ]
    chunks: list[str] = []
    current = ""
    for phrase in phrases:
        if len(current) + len(phrase) <= MAX_SUBTITLE_CHARS:
            current += phrase
            continue
        if current:
            chunks.append(current)
            current = ""
        while len(phrase) > MAX_SUBTITLE_CHARS:
            chunks.append(phrase[:MAX_SUBTITLE_CHARS])
            phrase = phrase[MAX_SUBTITLE_CHARS:]
        current = phrase
    if current:
        chunks.append(current)
    return chunks


def _wrap_subtitle(text: str) -> str:
    """保持单行字幕；超长文本已由 _subtitle_chunks 拆分。"""
    return re.sub(r"\s+", " ", text).strip()[:MAX_SUBTITLE_CHARS]


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
