"""Course intro/outro rendering with Pillow and FFmpeg."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from ..core.models import ProcessConfig


TEMPLATES = {
    "academic": {
        "layout": "diagonal_panel",
        "background": "#12324A",
        "panel": "#F6F8FB",
        "accent": "#D6A239",
        "text": "#F8FAFC",
        "muted": "#D7DEE8",
    },
    "modern": {
        "layout": "diagonal_panel",
        "background": "#1F2937",
        "panel": "#E8F1F2",
        "accent": "#2AA198",
        "text": "#FFFFFF",
        "muted": "#CBD5E1",
    },
    "minimal": {
        "layout": "diagonal_panel",
        "background": "#F4F6F7",
        "panel": "#243447",
        "accent": "#2563EB",
        "text": "#172033",
        "muted": "#4B5563",
    },
    "university": {
        "layout": "title_card",
        "background": "#102A43",
        "panel": "#FFFFFF",
        "accent": "#C59A3D",
        "text": "#F8FAFC",
        "muted": "#D8E2EE",
        "label": "在线开放课程",
    },
    "credits": {
        "layout": "credits_roll",
        "background": "#111827",
        "panel": "#E5E7EB",
        "accent": "#38BDF8",
        "text": "#F9FAFB",
        "muted": "#CBD5E1",
        "label": "课程回顾",
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
    intro_background_path: Optional[Path] = None,
    outro_background_path: Optional[Path] = None,
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
                background_path=intro_background_path,
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
                background_path=outro_background_path or intro_background_path,
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
    background_path: Optional[Path],
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
        background_path=background_path,
    )
    ffmpeg = shutil.which("ffmpeg")
    duration = _clip_duration(options, kind)
    enable_motion = bool(options.get("enable_motion", True))
    enable_music = bool(options.get("enable_music", True))
    motion_style = str(options.get("motion_style") or "zoom").strip().lower()
    video_filter = _video_filter(config, duration, enable_motion, motion_style)
    video_path = Path(str(options.get(f"{kind}_video_path") or ""))
    use_video_background = video_path.is_file()
    command = [ffmpeg, "-y"]
    if use_video_background:
        command.extend(["-stream_loop", "-1", "-t", f"{duration:.2f}", "-i", str(video_path)])
        command.extend(["-loop", "1", "-t", f"{duration:.2f}", "-i", str(image_path)])
        video_filter = (
            f"[0:v]scale={config.video_width}:{config.video_height}:force_original_aspect_ratio=increase,"
            f"crop={config.video_width}:{config.video_height},setsar=1[bg];"
            "[1:v]format=rgba,colorchannelmixer=aa=0.82[card];"
            f"[bg][card]overlay=shortest=1,{_video_filter(config, duration, enable_motion, motion_style)}"
        )
        next_input = 2
    else:
        command.extend(["-loop", "1", "-t", f"{duration:.2f}", "-i", str(image_path)])
        next_input = 1
    if enable_music:
        music_path = Path(str(options.get("music_path") or ""))
        if music_path.is_file():
            command.extend(["-stream_loop", "-1", "-t", f"{duration:.2f}", "-i", str(music_path)])
            music_input = next_input
            audio_filter = (
                f"[{music_input}:a]volume=0.16,afade=t=in:st=0:d=0.35,"
                f"afade=t=out:st={max(0.0, duration - 0.5):.2f}:d=0.45[a]"
            )
        else:
            for frequency in _music_frequencies(options):
                command.extend([
                    "-f", "lavfi", "-t", f"{duration:.2f}", "-i",
                    f"sine=frequency={frequency}:sample_rate={config.audio_sample_rate}",
                ])
            audio_filter = (
                f"[{next_input}:a][{next_input + 1}:a][{next_input + 2}:a]amix=inputs=3:duration=shortest,volume=0.018,"
                "afade=t=in:st=0:d=0.35,"
                f"afade=t=out:st={max(0.0, duration - 0.5):.2f}:d=0.45[a]"
            )
        filter_complex = f"{video_filter}[v];{audio_filter}" if use_video_background else f"[0:v]{video_filter}[v];{audio_filter}"
    else:
        command.extend([
            "-f",
            "lavfi",
            "-t",
            f"{duration:.2f}",
            "-i",
            f"anullsrc=channel_layout=mono:sample_rate={config.audio_sample_rate}",
        ])
        silence_input = next_input
        filter_complex = (
            f"{video_filter}[v];[{silence_input}:a]anull[a]"
            if use_video_background else f"[0:v]{video_filter}[v];[{silence_input}:a]anull[a]"
        )
    command.extend([
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "[a]",
    ])
    command.extend([
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
    ])
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
    background_path: Optional[Path],
) -> None:
    palette = _palette(options)
    width, height = config.video_width, config.video_height
    image = _base_background(
        width,
        height,
        palette,
        background_path if (_use_slide_background(options) or options.get("background_path")) else None,
        str(options.get("background_style") or "ppt").strip().lower(),
    )
    draw = ImageDraw.Draw(image)

    layout = palette.get("layout", "diagonal_panel")
    if layout == "title_card":
        _render_title_card_layout(
            image,
            draw,
            config,
            options,
            palette,
            kind=kind,
            course_title=course_title,
            segment_title=segment_title,
            logo_path=logo_path,
        )
    elif layout == "credits_roll":
        _render_credits_layout(
            image,
            draw,
            config,
            options,
            palette,
            kind=kind,
            course_title=course_title,
            segment_title=segment_title,
            logo_path=logo_path,
        )
    else:
        _render_diagonal_panel_layout(
            image,
            draw,
            config,
            options,
            palette,
            kind=kind,
            course_title=course_title,
            segment_title=segment_title,
            logo_path=logo_path,
        )

    image.save(output)


def _render_diagonal_panel_layout(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    config: ProcessConfig,
    options: dict,
    palette: dict,
    *,
    kind: str,
    course_title: str,
    segment_title: str,
    logo_path: Optional[Path],
) -> None:
    width, height = config.video_width, config.video_height

    accent = palette["accent"]
    draw.rectangle((0, 0, width, max(10, height // 80)), fill=accent)
    panel_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(panel_overlay)
    panel_draw.rectangle(
        (round(width * 0.64), 0, width, height),
        fill=(*_hex_to_rgb(palette["panel"]), 232),
    )
    composited = Image.alpha_composite(image.convert("RGBA"), panel_overlay).convert("RGB")
    image.paste(composited)
    draw = ImageDraw.Draw(image)
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

    left, content_y, max_text_width = _content_box(
        options, kind, width, height, default_x=8, default_y=30 if kind == "intro" else 34,
        default_width=50,
    )
    organization = str(options.get("organization") or "").strip()
    instructor = str(options.get("instructor") or "").strip()
    outro_text = str(options.get("outro_text") or "感谢观看").strip()
    intro_title = str(options.get("intro_title") or "").strip()
    intro_subtitle = str(options.get("intro_subtitle") or "").strip()
    outro_title = str(options.get("outro_title") or "").strip()
    outro_subtitle = str(options.get("outro_subtitle") or "").strip()
    title = intro_title or segment_title or course_title or "课程视频"

    if kind == "intro":
        y = content_y
        if organization:
            draw.text((left, y - round(height * 0.09)), organization, fill=palette["muted"], font=meta_font)
        for line in _wrap_text(draw, title, title_font, max_text_width, max_lines=3):
            draw.text((left, y), line, fill=palette["text"], font=title_font)
            y += round(height * 0.078)
        subtitle = intro_subtitle or (course_title if segment_title and course_title else "")
        if subtitle:
            draw.text((left, y + 12), subtitle, fill=palette["muted"], font=small_font)
        if instructor:
            draw.text(
                (left, round(height * 0.76)),
                f"主讲人：{instructor}",
                fill=palette["muted"],
                font=subtitle_font,
            )
    else:
        title = outro_title or segment_title or course_title or "课程视频"
        y = content_y
        for line in _wrap_text(draw, outro_text, title_font, max_text_width, max_lines=2):
            draw.text((left, y), line, fill=palette["text"], font=title_font)
            y += round(height * 0.078)
        draw.text((left, y + 24), outro_subtitle or title, fill=palette["muted"], font=subtitle_font)
        if organization:
            draw.text((left, round(height * 0.78)), organization, fill=palette["muted"], font=meta_font)

    if logo_path and logo_path.is_file():
        _paste_logo(image, logo_path, config, options)


def _render_title_card_layout(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    config: ProcessConfig,
    options: dict,
    palette: dict,
    *,
    kind: str,
    course_title: str,
    segment_title: str,
    logo_path: Optional[Path],
) -> None:
    width, height = config.video_width, config.video_height
    accent = palette["accent"]
    left = round(width * 0.095)
    right = round(width * 0.90)
    title = segment_title or course_title or "课程视频"
    organization = str(options.get("organization") or "").strip()
    instructor = str(options.get("instructor") or "").strip()
    outro_text = str(options.get("outro_text") or "感谢观看").strip()
    intro_title = str(options.get("intro_title") or "").strip()
    intro_subtitle = str(options.get("intro_subtitle") or "").strip()
    intro_label = str(options.get("intro_label") or palette.get("label") or "课程视频").strip()
    outro_title = str(options.get("outro_title") or "").strip()
    outro_subtitle = str(options.get("outro_subtitle") or "").strip()

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        (0, 0, width, height),
        fill=(*_hex_to_rgb(palette["background"]), 112),
    )
    overlay_draw.rectangle(
        (left, round(height * 0.17), right, round(height * 0.83)),
        outline=(*_hex_to_rgb(accent), 210),
        width=max(3, width // 360),
    )
    overlay_draw.rectangle(
        (left, round(height * 0.17), left + round(width * 0.012), round(height * 0.83)),
        fill=(*_hex_to_rgb(accent), 230),
    )
    image.alpha_composite(overlay) if image.mode == "RGBA" else None
    if image.mode != "RGBA":
        composited = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        image.paste(composited)

    title_font = _load_font(round(height * 0.068), bold=True)
    subtitle_font = _load_font(round(height * 0.034), bold=False)
    meta_font = _load_font(round(height * 0.026), bold=False)
    label_font = _load_font(round(height * 0.024), bold=True)
    text_left, content_y, text_width = _content_box(
        options, kind, width, height, default_x=15, default_y=36,
        default_width=68,
    )

    label = intro_label if kind == "intro" else str(options.get("outro_label") or "课程总结").strip()
    draw.rounded_rectangle(
        (
            text_left,
            round(height * 0.25),
            text_left + round(width * 0.16),
            round(height * 0.30),
        ),
        radius=max(6, height // 120),
        fill=accent,
    )
    draw.text(
        (text_left + round(width * 0.018), round(height * 0.257)),
        label,
        fill=palette["background"],
        font=label_font,
    )

    if kind == "intro":
        title = intro_title or title
        y = content_y
        for line in _wrap_text(draw, title, title_font, text_width, max_lines=2):
            draw.text((text_left, y), line, fill=palette["text"], font=title_font)
            y += round(height * 0.082)
        subtitle = intro_subtitle or (course_title if segment_title and course_title else "")
        if subtitle:
            draw.text((text_left, y + 10), subtitle, fill=palette["muted"], font=subtitle_font)
        meta = " · ".join(part for part in (organization, f"主讲人：{instructor}" if instructor else "") if part)
        if meta:
            draw.text((text_left, round(height * 0.70)), meta, fill=palette["muted"], font=meta_font)
    else:
        title = outro_title or title
        y = content_y
        for line in _wrap_text(draw, outro_text, title_font, text_width, max_lines=2):
            draw.text((text_left, y), line, fill=palette["text"], font=title_font)
            y += round(height * 0.082)
        draw.text((text_left, y + 12), outro_subtitle or title, fill=palette["muted"], font=subtitle_font)
        if organization:
            draw.text((text_left, round(height * 0.70)), organization, fill=palette["muted"], font=meta_font)

    draw.line(
        (text_left, round(height * 0.78), right - round(width * 0.055), round(height * 0.78)),
        fill=accent,
        width=max(2, height // 220),
    )
    if logo_path and logo_path.is_file():
        _paste_logo(image, logo_path, config, options)


def _render_credits_layout(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    config: ProcessConfig,
    options: dict,
    palette: dict,
    *,
    kind: str,
    course_title: str,
    segment_title: str,
    logo_path: Optional[Path],
) -> None:
    width, height = config.video_width, config.video_height
    title = segment_title or course_title or "课程视频"
    organization = str(options.get("organization") or "").strip()
    instructor = str(options.get("instructor") or "").strip()
    outro_text = str(options.get("outro_text") or "感谢观看").strip()
    intro_title = str(options.get("intro_title") or "").strip()
    intro_subtitle = str(options.get("intro_subtitle") or "").strip()
    intro_label = str(options.get("intro_label") or palette.get("label") or "课程回顾").strip()
    outro_title = str(options.get("outro_title") or "").strip()
    outro_subtitle = str(options.get("outro_subtitle") or "").strip()
    accent = palette["accent"]

    title_font = _load_font(round(height * 0.060), bold=True)
    line_font = _load_font(round(height * 0.035), bold=False)
    meta_font = _load_font(round(height * 0.026), bold=False)
    left, content_y, max_text_width = _content_box(
        options, kind, width, height, default_x=16, default_y=30,
        default_width=68,
    )

    for index in range(9):
        y = round(height * (0.16 + index * 0.075))
        alpha = max(26, 120 - index * 9)
        line_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        line_draw = ImageDraw.Draw(line_overlay)
        line_draw.line(
            (left, y, width - left, y),
            fill=(*_hex_to_rgb(accent), alpha),
            width=max(1, height // 360),
        )
        image.paste(Image.alpha_composite(image.convert("RGBA"), line_overlay).convert("RGB"))

    if kind == "intro":
        heading = intro_title or title
        support_lines = [intro_subtitle or intro_label]
        if organization:
            support_lines.append(organization)
        if instructor:
            support_lines.append(f"主讲人：{instructor}")
    else:
        heading = outro_text or outro_title or "感谢观看"
        support_lines = [outro_subtitle or outro_title or title]
        if organization:
            support_lines.append(organization)

    y = content_y
    for line in _wrap_text(draw, heading, title_font, max_text_width, max_lines=2):
        draw.text((left, y), line, fill=palette["text"], font=title_font)
        y += round(height * 0.080)
    y += round(height * 0.025)
    for line in support_lines[:4]:
        draw.text((left, y), str(line), fill=palette["muted"], font=line_font)
        y += round(height * 0.052)
    draw.text(
        (left, round(height * 0.80)),
        "Powered by VidPPT",
        fill=palette["muted"],
        font=meta_font,
    )
    if logo_path and logo_path.is_file():
        _paste_logo(image, logo_path, config, options)


def _base_background(
    width: int,
    height: int,
    palette: dict,
    background_path: Optional[Path],
    background_style: str = "ppt",
) -> Image.Image:
    if background_path and background_path.is_file() and background_style == "ppt":
        source = Image.open(background_path).convert("RGB")
        source = ImageOps.fit(
            source,
            (width, height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        source = source.filter(ImageFilter.GaussianBlur(radius=max(10, width // 95)))
        shade = Image.new("RGBA", (width, height), (*_hex_to_rgb(palette["background"]), 172))
        return Image.alpha_composite(source.convert("RGBA"), shade).convert("RGB")
    if background_style == "gradient":
        top = _hex_to_rgb(palette["background"])
        bottom = tuple(max(0, channel - 34) for channel in top)
        image = Image.new("RGB", (width, height), top)
        draw = ImageDraw.Draw(image)
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(round(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
            draw.line((0, y, width, y), fill=color)
        return image
    if background_style == "light":
        return Image.new("RGB", (width, height), palette.get("panel") or "#F8FAFC")
    return Image.new("RGB", (width, height), palette["background"])


def _palette(options: dict) -> dict:
    palette = dict(TEMPLATES.get(options.get("template"), TEMPLATES["academic"]))
    accent = str(options.get("accent_color") or "").strip()
    if _is_hex_color(accent):
        palette["accent"] = accent
    return palette


def _is_hex_color(value: str) -> bool:
    cleaned = str(value or "").strip().lstrip("#")
    return len(cleaned) == 6 and all(char in "0123456789abcdefABCDEF" for char in cleaned)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = str(value or "#000000").strip().lstrip("#")
    if len(cleaned) != 6:
        return (0, 0, 0)
    return tuple(int(cleaned[index:index + 2], 16) for index in (0, 2, 4))


def _use_slide_background(options: dict) -> bool:
    if str(options.get("background_style") or "ppt").strip().lower() != "ppt":
        return False
    return bool(options.get("use_slide_background", True))


def _content_box(
    options: dict,
    kind: str,
    width: int,
    height: int,
    *,
    default_x: float,
    default_y: float,
    default_width: float,
) -> tuple[int, int, int]:
    def percent(name: str, default: float, minimum: float = 0.0) -> float:
        try:
            value = float(options.get(name, default))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(100.0, value))

    x = percent(f"{kind}_content_x", default_x)
    y = percent(f"{kind}_content_y", default_y)
    box_width = percent(f"{kind}_content_width", default_width, 18.0)
    box_width = min(box_width, 100.0 - x)
    return round(width * x / 100), round(height * y / 100), round(width * box_width / 100)


def _clip_duration(options: dict, kind: str) -> float:
    specific = options.get(f"{kind}_duration_seconds")
    fallback = options.get("duration_seconds", 4.0)
    try:
        return max(1.0, float(specific if specific not in (None, "") else fallback))
    except (TypeError, ValueError):
        return 4.0


def _video_filter(
    config: ProcessConfig,
    duration: float,
    enable_motion: bool,
    motion_style: str,
) -> str:
    base = f"scale={config.video_width}:{config.video_height},format={config.video_pixel_format}"
    if not enable_motion or motion_style == "none":
        return base
    frames = max(1, round(duration * config.video_fps))
    if motion_style == "pan":
        return (
            f"scale={round(config.video_width * 1.08)}:{round(config.video_height * 1.08)},"
            f"crop={config.video_width}:{config.video_height}:x='(iw-ow)*on/{frames}':y='(ih-oh)/2',"
            "fade=t=in:st=0:d=0.35,"
            f"fade=t=out:st={max(0.0, duration - 0.45):.2f}:d=0.35,"
            f"format={config.video_pixel_format}"
        )
    return (
        "scale=iw*1.04:ih*1.04,"
        f"zoompan=z='min(zoom+0.0008,1.04)':"
        f"d={frames}:"
        f"s={config.video_width}x{config.video_height}:fps={config.video_fps},"
        "fade=t=in:st=0:d=0.35,"
        f"fade=t=out:st={max(0.0, duration - 0.45):.2f}:d=0.35,"
        f"format={config.video_pixel_format}"
    )


def _music_frequencies(options: dict) -> tuple[str, str, str]:
    style = str(options.get("music_style") or "warm").strip().lower()
    if style == "bright":
        return ("262", "330", "392")
    if style == "calm":
        return ("174", "220", "261")
    if style == "tech":
        return ("220", "277", "370")
    return ("196", "247", "294")


def _paste_logo(image: Image.Image, logo_path: Path, config: ProcessConfig, options: dict) -> None:
    position = str(options.get("logo_position") or "top-right").strip().lower()
    if position == "none":
        return
    logo = Image.open(logo_path).convert("RGBA")
    max_width = round(config.video_width * 0.18)
    max_height = round(config.video_height * 0.16)
    logo.thumbnail((max_width, max_height))
    margin_x = round(config.video_width * 0.065)
    margin_y = round(config.video_height * 0.10)
    if position.endswith("left"):
        x = margin_x
    else:
        x = config.video_width - margin_x - logo.width
    if position.startswith("bottom"):
        y = config.video_height - margin_y - logo.height
    else:
        y = margin_y
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
