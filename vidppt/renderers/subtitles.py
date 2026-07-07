"""根据逐页讲稿与音频时长生成基础 SRT 字幕。"""

from pathlib import Path

from ..core.course import CourseSection
from ..utils.subtitle_rules import (
    MAX_SUBTITLE_CHARS,
    subtitle_chunks,
    wrap_subtitle,
)


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
    """按语义停顿与每屏行数限制切成适合画面展示的字幕。"""
    return subtitle_chunks(text)


def _wrap_subtitle(text: str) -> str:
    """把单条字幕整理为最多两行。"""
    return wrap_subtitle(text)


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
