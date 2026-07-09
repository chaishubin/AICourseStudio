"""Course intro/outro rendering with Pillow and FFmpeg."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from ..core.models import ProcessConfig


TEMPLATES = {
    "academic": {
        "background": "#12324A",
        "panel": "#F6F8FB",
        "accent": "#D6A239",
        "text": "#F8FAFC",
        "muted": "#D7DEE8",
    },
    "modern": {
        "background": "#1F2937",
        "panel": "#E8F1F2",
        "accent": "#2AA198",
        "text": "#FFFFFF",
        "muted": "#CBD5E1",
    },
    "minimal": {
        "background": "#F4F6F7",
        "panel": "#243447",
        "accent": "#2563EB",
        "text": "#172033",
        "muted": "#4B5563",
    },
}


def package_course_video(
    source_video: Path,
    output_video: Path,
    config: ProcessConfig,
    options: dict,
    *,
    course_title: str,
    segment_title: str = "",
    logo_path: Optional[Path] = None,
    cancel_check=None,
) -> None:
    """Add optional intro/outro clips around an existing MP4."""
    if not options.get("enable_intro") and not options.get("enable_outro"):
        if source_video != output_video:
            source_video.replace(output_video)
        return

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("生成片头片尾需要 ffmpeg，但当前环境未找到该命令")

    output_video.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="course_packaging_", dir=str(output_video.parent)
    ) as temp_name:
        temp_dir = Path(temp_name)
        clips = []
        if options.get("enable_intro"):
            intro = temp_dir / "intro.mp4"
            _render_packaging_clip(
                intro,
                config,
                options,
                kind="intro",
                course_title=course_title,
                segment_title=segment_title,
                logo_path=logo_path,
            )
            clips.append(intro)
        clips.append(source_video)
        if options.get("enable_outro"):
            outro = temp_dir / "outro.mp4"
            _render_packaging_clip(
                outro,
                config,
                options,
                kind="outro",
                course_title=course_title,
                segment_title=segment_title,
                logo_path=logo_path,
            )
            clips.append(outro)

        packaged = temp_dir / "packaged.mp4"
        _concat_with_ffmpeg(ffmpeg, clips, packaged, config, cancel_check)
        packaged.replace(output_video)


def _render_packaging_clip(
    output: Path,
    config: ProcessConfig,
    options: dict,
    *,
    kind: str,
    course_title: str,
    segment_title: str,
    logo_path: Optional[Path],
) -> None:
    image_path = output.with_suffix(".png")
    _render_packaging_image(
        image_path,
        config,
        options,
        kind=kind,
        course_title=course_title,
        segment_title=segment_title,
        logo_path=logo_path,
    )
    ffmpeg = shutil.which("ffmpeg")
    duration = max(1.0, float(options.get("duration_seconds", 4.0)))
    command = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-t",
        f"{duration:.2f}",
        "-i",
        str(image_path),
        "-f",
        "lavfi",
        "-t",
        f"{duration:.2f}",
        "-i",
        f"anullsrc=channel_layout=mono:sample_rate={config.audio_sample_rate}",
        "-c:v",
        config.video_codec,
        "-preset",
        config.video_preset,
        "-crf",
        str(config.video_crf),
        "-profile:v",
        config.video_profile,
        "-pix_fmt",
        config.video_pixel_format,
        "-r",
        str(config.video_fps),
        "-g",
        str(config.video_fps * config.video_gop_seconds),
        "-c:a",
        config.audio_codec,
        "-b:a",
        config.audio_bitrate,
        "-ar",
        str(config.audio_sample_rate),
        "-ac",
        str(config.audio_channels),
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def _render_packaging_image(
    output: Path,
    config: ProcessConfig,
    options: dict,
    *,
    kind: str,
    course_title: str,
    segment_title: str,
    logo_path: Optional[Path],
) -> None:
    palette = TEMPLATES.get(options.get("template"), TEMPLATES["academic"])
    width, height = config.video_width, config.video_height
    image = Image.new("RGB", (width, height), palette["background"])
    draw = ImageDraw.Draw(image)

    accent = palette["accent"]
    draw.rectangle((0, 0, width, max(10, height // 80)), fill=accent)
    draw.rectangle((round(width * 0.64), 0, width, height), fill=palette["panel"])
    draw.polygon(
        [
            (int(width * 0.58), 0),
            (int(width * 0.72), 0),
            (int(width * 0.64), height),
            (int(width * 0.50), height),
        ],
        fill=accent,
    )

    title_font = _load_font(round(height * 0.064), bold=True)
    subtitle_font = _load_font(round(height * 0.034), bold=False)
    meta_font = _load_font(round(height * 0.027), bold=False)
    small_font = _load_font(round(height * 0.022), bold=False)

    left = round(width * 0.08)
    max_text_width = round(width * 0.50)
    organization = str(options.get("organization") or "").strip()
    instructor = str(options.get("instructor") or "").strip()
    outro_text = str(options.get("outro_text") or "感谢观看").strip()
    title = segment_title or course_title or "课程视频"

    if kind == "intro":
        y = round(height * 0.30)
        if organization:
            draw.text((left, y - round(height * 0.09)), organization, fill=palette["muted"], font=meta_font)
        for line in _wrap_text(draw, title, title_font, max_text_width, max_lines=3):
            draw.text((left, y), line, fill=palette["text"], font=title_font)
            y += round(height * 0.078)
        if segment_title and course_title:
            draw.text((left, y + 12), course_title, fill=palette["muted"], font=small_font)
        if instructor:
            draw.text(
                (left, round(height * 0.76)),
                f"主讲人：{instructor}",
                fill=palette["muted"],
                font=subtitle_font,
            )
    else:
        y = round(height * 0.34)
        for line in _wrap_text(draw, outro_text, title_font, max_text_width, max_lines=2):
            draw.text((left, y), line, fill=palette["text"], font=title_font)
            y += round(height * 0.078)
        draw.text((left, y + 24), title, fill=palette["muted"], font=subtitle_font)
        if organization:
            draw.text((left, round(height * 0.78)), organization, fill=palette["muted"], font=meta_font)

    if logo_path and logo_path.is_file():
        _paste_logo(image, logo_path, config)

    image.save(output)


def _paste_logo(image: Image.Image, logo_path: Path, config: ProcessConfig) -> None:
    logo = Image.open(logo_path).convert("RGBA")
    max_width = round(config.video_width * 0.18)
    max_height = round(config.video_height * 0.16)
    logo.thumbnail((max_width, max_height))
    x = round(config.video_width * 0.76)
    y = round(config.video_height * 0.16)
    image.paste(logo, (x, y), logo)


def _concat_with_ffmpeg(
    ffmpeg: str,
    clips: list[Path],
    output: Path,
    config: ProcessConfig,
    cancel_check=None,
) -> None:
    clips = [
        _ensure_audio_stream(ffmpeg, clip, output.parent, config)
        for clip in clips
    ]
    command = [ffmpeg, "-y"]
    for clip in clips:
        command.extend(["-i", str(clip)])
    parts = []
    for index in range(len(clips)):
        parts.append(f"[{index}:v:0][{index}:a:0]")
    filter_complex = "".join(parts) + f"concat=n={len(clips)}:v=1:a=1[v][a]"
    command.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            config.video_codec,
            "-preset",
            config.video_preset,
            "-crf",
            str(config.video_crf),
            "-profile:v",
            config.video_profile,
            "-pix_fmt",
            config.video_pixel_format,
            "-r",
            str(config.video_fps),
            "-g",
            str(config.video_fps * config.video_gop_seconds),
            "-c:a",
            config.audio_codec,
            "-b:a",
            config.audio_bitrate,
            "-ar",
            str(config.audio_sample_rate),
            "-ac",
            str(config.audio_channels),
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    while process.poll() is None:
        if cancel_check and cancel_check():
            process.terminate()
            process.wait(timeout=5)
            output.unlink(missing_ok=True)
            raise InterruptedError("用户停止了视频生成")
        time.sleep(0.2)
    if process.returncode != 0:
        _, stderr = process.communicate()
        raise subprocess.CalledProcessError(process.returncode, command, stderr=stderr)


def _ensure_audio_stream(
    ffmpeg: str,
    clip: Path,
    temp_dir: Path,
    config: ProcessConfig,
) -> Path:
    if _has_audio_stream(clip):
        return clip
    output = temp_dir / f"{clip.stem}.with_audio.mp4"
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(clip),
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=mono:sample_rate={config.audio_sample_rate}",
        "-c:v",
        "copy",
        "-c:a",
        config.audio_codec,
        "-b:a",
        config.audio_bitrate,
        "-ar",
        str(config.audio_sample_rate),
        "-ac",
        str(config.audio_channels),
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return output


def _has_audio_stream(clip: Path) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                str(clip),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return True
    return bool(result.stdout.strip())


def _load_font(size: int, *, bold: bool = False):
    families = [
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "WenQuanYi Zen Hei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    for family in families:
        path = _font_path(f"{family}:style={'Bold' if bold else 'Regular'}")
        if path:
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _font_path(pattern: str) -> str:
    fc_match = shutil.which("fc-match")
    if not fc_match:
        return ""
    try:
        result = subprocess.run(
            [fc_match, "-f", "%{file}", pattern],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int):
    text = str(text or "").strip() or "课程视频"
    lines = []
    current = ""
    for char in text:
        candidate = current + char
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = char
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len("".join(lines)) < len(text):
        lines[-1] = lines[-1].rstrip("，。,. ") + "..."
    return lines
