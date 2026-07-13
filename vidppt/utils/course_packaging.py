"""Course intro/outro rendering with Pillow and FFmpeg."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import re
from pathlib import Path
from typing import Optional

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

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
    mid_background_path: Optional[Path] = None,
    outro_background_path: Optional[Path] = None,
    segment_durations: Optional[list[float]] = None,
    cancel_check=None,
) -> None:
    """Add optional intro, inter-segment transitions, and outro around an MP4."""
    use_mid = bool(options.get("enable_mid")) and bool(segment_durations) and len(segment_durations) > 1
    if not options.get("enable_intro") and not use_mid and not options.get("enable_outro"):
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
        if use_mid:
            mid = temp_dir / "mid.mp4"
            _render_packaging_clip(
                mid,
                config,
                options,
                kind="mid",
                course_title=course_title,
                segment_title="下一章节",
                logo_path=logo_path,
                background_path=mid_background_path or intro_background_path,
            )
            offset = 0.0
            for index, duration in enumerate(segment_durations):
                chunk = temp_dir / f"segment_{index + 1:03d}.mp4"
                _extract_video_range(
                    ffmpeg,
                    source_video,
                    chunk,
                    config,
                    start=offset,
                    duration=None if index == len(segment_durations) - 1 else duration,
                )
                clips.append(chunk)
                offset += duration
                if index < len(segment_durations) - 1:
                    clips.append(mid)
        else:
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
        _concat_with_ffmpeg(
            ffmpeg,
            clips,
            packaged,
            config,
            cancel_check,
            transition_seconds=float(options.get("transition_seconds") or 0.35),
        )
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
    options = _side_options(options, kind)
    background_path = Path(options["background_path"]) if options.get("background_path") else background_path
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
    staged_motion = enable_motion and motion_style != "none"
    decor_path = output.with_name(f"{output.stem}.decor.png")
    title_stage_path = output.with_name(f"{output.stem}.title-stage.png")
    title_layer_path = output.with_name(f"{output.stem}.title-layer.png")
    meta_layer_path = output.with_name(f"{output.stem}.meta-layer.png")
    if staged_motion:
        _render_packaging_image(
            decor_path,
            config,
            {**options, "_reveal_stage": "decor"},
            kind=kind,
            course_title=course_title,
            segment_title=segment_title,
            logo_path=logo_path,
            background_path=background_path,
        )
        _render_packaging_image(
            title_stage_path,
            config,
            {**options, "_reveal_stage": "title"},
            kind=kind,
            course_title=course_title,
            segment_title=segment_title,
            logo_path=logo_path,
            background_path=background_path,
        )
        _difference_layer(decor_path, title_stage_path, title_layer_path)
        _difference_layer(title_stage_path, image_path, meta_layer_path)
    base_image_path = decor_path if staged_motion else image_path
    video_path = Path(str(options.get(f"{kind}_video_path") or ""))
    use_video_background = video_path.is_file()
    command = [ffmpeg, "-y"]
    if use_video_background:
        command.extend(["-stream_loop", "-1", "-t", f"{duration:.2f}", "-i", str(video_path)])
        command.extend(["-loop", "1", "-t", f"{duration:.2f}", "-i", str(base_image_path)])
        next_input = 2
    else:
        command.extend(["-loop", "1", "-t", f"{duration:.2f}", "-i", str(base_image_path)])
        next_input = 1
    if staged_motion:
        command.extend(["-loop", "1", "-t", f"{duration:.2f}", "-i", str(title_layer_path)])
        title_input = next_input
        next_input += 1
        command.extend(["-loop", "1", "-t", f"{duration:.2f}", "-i", str(meta_layer_path)])
        meta_input = next_input
        next_input += 1
        video_filter = _staged_video_filter(
            config,
            duration,
            motion_style,
            use_video_background=use_video_background,
            title_input=title_input,
            meta_input=meta_input,
        )
    elif use_video_background:
        video_filter = (
            f"[0:v]scale={config.video_width}:{config.video_height}:force_original_aspect_ratio=increase,"
            f"crop={config.video_width}:{config.video_height},setsar=1[bg];"
            "[1:v]format=rgba,colorchannelmixer=aa=0.82[card];"
            f"[bg][card]overlay=shortest=1,{_video_filter(config, duration, False, 'none')}"
        )
    else:
        video_filter = f"[0:v]{_video_filter(config, duration, False, 'none')}"
    if enable_music:
        music_path = Path(str(options.get("music_path") or ""))
        if music_path.is_file():
            command.extend(["-stream_loop", "-1", "-t", f"{duration:.2f}", "-i", str(music_path)])
            music_input = next_input
            audio_filter = (
                f"[{music_input}:a]loudnorm=I=-24:TP=-3:LRA=5,afade=t=in:st=0:d=0.30,"
                f"afade=t=out:st={max(0.0, duration - 0.5):.2f}:d=0.45[a]"
            )
        else:
            frequencies = _music_frequencies(options)
            for frequency in frequencies:
                command.extend([
                    "-f", "lavfi", "-t", f"{duration:.2f}", "-i",
                    f"sine=frequency={frequency}:sample_rate={config.audio_sample_rate}",
                ])
            audio_filter = _soundmark_filter(next_input, duration, len(frequencies))
        filter_complex = f"{video_filter}[v];{audio_filter}"
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
        filter_complex = f"{video_filter}[v];[{silence_input}:a]anull[a]"
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
        "-t",
        f"{duration:.2f}",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ])
    subprocess.run(command, check=True, capture_output=True, text=True)


def _difference_layer(before_path: Path, after_path: Path, output_path: Path) -> None:
    """Extract pixels introduced by a reveal stage into an RGBA overlay."""
    before = Image.open(before_path).convert("RGB")
    after = Image.open(after_path).convert("RGB")
    difference = ImageChops.difference(before, after)
    alpha = difference.convert("L").point(lambda value: min(255, value * 5))
    layer = after.convert("RGBA")
    layer.putalpha(alpha)
    layer.save(output_path)


def _staged_video_filter(
    config: ProcessConfig,
    duration: float,
    motion_style: str,
    *,
    use_video_background: bool,
    title_input: int,
    meta_input: int,
) -> str:
    """Build background motion followed by staged title and identity reveals."""
    motion = _video_filter(
        config,
        duration,
        True,
        motion_style,
        include_fades=False,
    )
    if use_video_background:
        base = (
            f"[0:v]scale={config.video_width}:{config.video_height}:force_original_aspect_ratio=increase,"
            f"crop={config.video_width}:{config.video_height},setsar=1,{motion}[moving];"
            "[1:v]format=rgba,colorchannelmixer=aa=0.82[decor];"
            "[moving][decor]overlay=shortest=1[base]"
        )
    else:
        base = f"[0:v]{motion}[base]"
    title_start = min(0.35, max(0.05, duration * 0.10))
    meta_start = min(1.10, max(title_start + 0.25, duration * 0.28))
    fade_out_start = max(0.0, duration - 0.42)
    return (
        f"{base};"
        f"[{title_input}:v]format=rgba,fade=t=in:st={title_start:.2f}:d=0.48:alpha=1[title];"
        f"[base][title]overlay=x='-24+24*min(max((t-{title_start:.2f})/0.55,0),1)':y=0:shortest=1[titled];"
        f"[{meta_input}:v]format=rgba,fade=t=in:st={meta_start:.2f}:d=0.42:alpha=1[meta];"
        f"[titled][meta]overlay=shortest=1,fade=t=in:st=0:d=0.28,"
        f"fade=t=out:st={fade_out_start:.2f}:d=0.36,format={config.video_pixel_format}"
    )


def _soundmark_filter(first_input: int, duration: float, input_count: int) -> str:
    """Create a short, shaped course ident instead of an inaudible flat chord."""
    main_count = max(1, input_count - 1)
    pieces = []
    labels = []
    for index in range(main_count):
        delay_ms = index * 110
        local_duration = max(0.6, duration - delay_ms / 1000)
        fade_out = max(0.15, local_duration - 0.55)
        label = f"tone{index}"
        pieces.append(
            f"[{first_input + index}:a]atrim=0:{local_duration:.2f},"
            f"afade=t=in:st=0:d=0.10,afade=t=out:st={fade_out:.2f}:d=0.48,"
            f"adelay={delay_ms}:all=1[{label}]"
        )
        labels.append(f"[{label}]")
    stinger_index = first_input + input_count - 1
    stinger_delay = max(0, round((duration - 0.75) * 1000))
    pieces.append(
        f"[{stinger_index}:a]atrim=0:0.65,afade=t=in:st=0:d=0.04,"
        f"afade=t=out:st=0.22:d=0.40,adelay={stinger_delay}:all=1[stinger]"
    )
    labels.append("[stinger]")
    pieces.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
        "aecho=0.8:0.32:55:0.10,loudnorm=I=-24:TP=-4:LRA=4,"
        f"atrim=0:{duration:.2f}[a]"
    )
    return ";".join(pieces)


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
    options = _side_options(options, kind)
    background_path = Path(options["background_path"]) if options.get("background_path") else background_path
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
    reveal_stage = str(options.get("_reveal_stage") or "full")

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
    if reveal_stage == "decor":
        return

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
        if organization and reveal_stage == "full":
            draw.text((left, y - round(height * 0.09)), organization, fill=palette["muted"], font=meta_font)
        for line in _wrap_text(draw, title, title_font, max_text_width, max_lines=3):
            draw.text((left, y), line, fill=palette["text"], font=title_font)
            y += round(height * 0.078)
        subtitle = intro_subtitle or (course_title if segment_title and course_title else "")
        if subtitle:
            draw.text((left, y + 12), subtitle, fill=palette["muted"], font=small_font)
        if instructor and reveal_stage == "full":
            instructor_meta = _instructor_meta(options, instructor)
            draw.text(
                (left, round(height * 0.76)),
                instructor_meta,
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
        if organization and reveal_stage == "full":
            draw.text((left, round(height * 0.78)), organization, fill=palette["muted"], font=meta_font)

    if reveal_stage == "full" and logo_path and logo_path.is_file():
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
    reveal_stage = str(options.get("_reveal_stage") or "full")
    accent = palette["accent"]
    title = segment_title or course_title or "课程视频"
    organization = str(options.get("organization") or "").strip()
    instructor = str(options.get("instructor") or "").strip()
    outro_text = str(options.get("outro_text") or "感谢观看").strip()
    intro_title = str(options.get("intro_title") or "").strip()
    intro_subtitle = str(options.get("intro_subtitle") or "").strip()
    intro_label = str(options.get("intro_label") or palette.get("label") or "课程视频").strip()
    outro_title = str(options.get("outro_title") or "").strip()
    outro_subtitle = str(options.get("outro_subtitle") or "").strip()
    text_left, content_y, text_width = _content_box(
        options, kind, width, height, default_x=15, default_y=36,
        default_width=68,
    )
    rail_x = max(round(width * 0.035), text_left - round(width * 0.045))
    rail_top = round(height * 0.20)
    rail_bottom = round(height * 0.80)
    corner_right = min(round(width * 0.92), text_left + text_width)
    accent_rgb = _hex_to_rgb(accent)

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle(
        (0, 0, width, height),
        fill=(*_hex_to_rgb(palette["background"]), 112),
    )
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.rounded_rectangle(
        (
            rail_x - round(width * 0.006),
            rail_top,
            rail_x + round(width * 0.006),
            rail_bottom,
        ),
        radius=max(4, width // 240),
        fill=(*accent_rgb, 150),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(5, width // 150)))
    overlay = Image.alpha_composite(overlay, glow)
    overlay_draw = ImageDraw.Draw(overlay)
    rail_width = max(4, width // 250)
    overlay_draw.rounded_rectangle(
        (rail_x, rail_top, rail_x + rail_width, rail_bottom),
        radius=max(2, rail_width // 2),
        fill=(*accent_rgb, 205),
    )
    corner_length = round(width * 0.075)
    corner_height = round(height * 0.045)
    corner_width = max(2, width // 520)
    overlay_draw.line(
        (corner_right - corner_length, rail_top, corner_right, rail_top),
        fill=(*accent_rgb, 115),
        width=corner_width,
    )
    overlay_draw.line(
        (corner_right, rail_top, corner_right, rail_top + corner_height),
        fill=(*accent_rgb, 115),
        width=corner_width,
    )
    overlay_draw.line(
        (rail_x, rail_bottom, rail_x + round(width * 0.06), rail_bottom),
        fill=(*accent_rgb, 105),
        width=corner_width,
    )
    image.alpha_composite(overlay) if image.mode == "RGBA" else None
    if image.mode != "RGBA":
        composited = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        image.paste(composited)
    if reveal_stage == "decor":
        return

    draw = ImageDraw.Draw(image)
    title_font = _load_font(round(height * 0.074), bold=True)
    subtitle_font = _load_font(round(height * 0.031), bold=False)
    meta_font = _load_font(round(height * 0.024), bold=False)
    label_font = _load_font(round(height * 0.021), bold=True)

    label = intro_label if kind == "intro" else str(options.get("outro_label") or "课程总结").strip()
    label_bbox = draw.textbbox((0, 0), label, font=label_font)
    label_padding_x = round(width * 0.013)
    label_padding_y = round(height * 0.008)
    label_top = max(rail_top + round(height * 0.035), content_y - round(height * 0.12))
    label_width = label_bbox[2] - label_bbox[0] + label_padding_x * 2
    label_height = label_bbox[3] - label_bbox[1] + label_padding_y * 2
    label_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    label_draw = ImageDraw.Draw(label_layer)
    label_draw.rounded_rectangle(
        (text_left, label_top, text_left + label_width, label_top + label_height),
        radius=max(7, label_height // 3),
        fill=(*accent_rgb, 34),
        outline=(*accent_rgb, 118),
        width=max(1, width // 960),
    )
    composited = Image.alpha_composite(image.convert("RGBA"), label_layer).convert("RGB")
    image.paste(composited)
    draw = ImageDraw.Draw(image)
    draw.text(
        (text_left + label_padding_x, label_top + label_padding_y - label_bbox[1]),
        label,
        fill=_blend_hex_colors(accent, palette["text"], 0.32),
        font=label_font,
    )

    if kind == "intro":
        title = intro_title or title
        y = content_y
        for line in _wrap_text(draw, title, title_font, text_width, max_lines=2):
            draw.text((text_left, y), line, fill=palette["text"], font=title_font)
            y += round(height * 0.086)
        draw.rounded_rectangle(
            (
                text_left,
                y + round(height * 0.010),
                text_left + round(width * 0.065),
                y + round(height * 0.016),
            ),
            radius=max(2, height // 300),
            fill=accent,
        )
        subtitle = intro_subtitle or (course_title if segment_title and course_title else "")
        if subtitle:
            draw.text(
                (text_left, y + round(height * 0.035)),
                subtitle,
                fill=palette["muted"],
                font=subtitle_font,
            )
        meta = _course_identity_meta(options, organization, instructor)
        if meta and reveal_stage == "full":
            meta_y = round(height * 0.715)
            dot_radius = max(3, height // 180)
            draw.ellipse(
                (text_left, meta_y + dot_radius, text_left + dot_radius * 2, meta_y + dot_radius * 3),
                fill=accent,
            )
            draw.text(
                (text_left + dot_radius * 4, meta_y),
                meta,
                fill=palette["muted"],
                font=meta_font,
            )
    else:
        title = outro_title or title
        y = content_y
        for line in _wrap_text(draw, outro_text, title_font, text_width, max_lines=2):
            draw.text((text_left, y), line, fill=palette["text"], font=title_font)
            y += round(height * 0.086)
        draw.rounded_rectangle(
            (text_left, y + round(height * 0.010), text_left + round(width * 0.065), y + round(height * 0.016)),
            radius=max(2, height // 300),
            fill=accent,
        )
        draw.text(
            (text_left, y + round(height * 0.035)),
            outro_subtitle or title,
            fill=palette["muted"],
            font=subtitle_font,
        )
        if organization and reveal_stage == "full":
            meta_y = round(height * 0.715)
            dot_radius = max(3, height // 180)
            draw.ellipse(
                (text_left, meta_y + dot_radius, text_left + dot_radius * 2, meta_y + dot_radius * 3),
                fill=accent,
            )
            draw.text(
                (text_left + dot_radius * 4, meta_y),
                organization,
                fill=palette["muted"],
                font=meta_font,
            )

    if reveal_stage == "full" and logo_path and logo_path.is_file():
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
    reveal_stage = str(options.get("_reveal_stage") or "full")
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

    if reveal_stage == "decor":
        return

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
    visible_support = support_lines[:1] if reveal_stage == "title" else support_lines[:4]
    for line in visible_support:
        draw.text((left, y), str(line), fill=palette["muted"], font=line_font)
        y += round(height * 0.052)
    if reveal_stage == "full":
        copyright_text = str(options.get("copyright") or "Powered by VidPPT").strip()
        draw.text(
            (left, round(height * 0.80)),
            copyright_text,
            fill=palette["muted"],
            font=meta_font,
        )
    if reveal_stage == "full" and logo_path and logo_path.is_file():
        _paste_logo(image, logo_path, config, options)


def _instructor_meta(options: dict, instructor: str) -> str:
    title = str(options.get("instructor_title") or "").strip()
    return f"主讲人：{instructor}{f' · {title}' if title else ''}"


def _course_identity_meta(options: dict, organization: str, instructor: str) -> str:
    department = str(options.get("department") or "").strip()
    organization_meta = " · ".join(part for part in (organization, department) if part)
    instructor_meta = _instructor_meta(options, instructor) if instructor else ""
    return " · ".join(part for part in (organization_meta, instructor_meta) if part)


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


def _blend_hex_colors(first: str, second: str, second_ratio: float) -> tuple[int, int, int]:
    """Blend two palette colors for restrained accent text."""
    ratio = max(0.0, min(1.0, float(second_ratio)))
    first_rgb = _hex_to_rgb(first)
    second_rgb = _hex_to_rgb(second)
    return tuple(
        round(first_rgb[index] * (1 - ratio) + second_rgb[index] * ratio)
        for index in range(3)
    )


def _use_slide_background(options: dict) -> bool:
    if str(options.get("background_style") or "ppt").strip().lower() != "ppt":
        return False
    return bool(options.get("use_slide_background", True))


def _side_options(options: dict, kind: str) -> dict:
    """将片头或片尾的独立设置映射到现有渲染字段。"""
    resolved = dict(options)
    for name in (
        "background_path", "music_path", "accent_color", "background_style",
        "logo_position", "motion_style", "music_style", "use_slide_background",
        "enable_motion", "enable_music",
    ):
        specific = options.get(f"{kind}_{name}")
        if specific is not None:
            resolved[name] = specific
    if kind == "mid":
        resolved["outro_text"] = options.get("mid_title") or "章节过渡"
        resolved["outro_title"] = options.get("mid_title") or "章节过渡"
        resolved["outro_subtitle"] = options.get("mid_subtitle") or "接下来进入下一章节"
        resolved["outro_label"] = options.get("mid_label") or "课程继续"
    return resolved


def _extract_video_range(
    ffmpeg: str,
    source: Path,
    output: Path,
    config: ProcessConfig,
    *,
    start: float,
    duration: Optional[float],
) -> None:
    """Extract a normalized course segment for transition-aware concatenation."""
    command = [ffmpeg, "-y", "-ss", f"{max(0.0, start):.3f}", "-i", str(source)]
    if duration is not None:
        command.extend(["-t", f"{max(0.05, duration):.3f}"])
    command.extend([
        "-c:v", config.video_codec,
        "-preset", config.video_preset,
        "-crf", str(config.video_crf),
        "-profile:v", config.video_profile,
        "-pix_fmt", config.video_pixel_format,
        "-r", str(config.video_fps),
        "-g", str(config.video_fps * config.video_gop_seconds),
        "-c:a", config.audio_codec,
        "-b:a", config.audio_bitrate,
        "-ar", str(config.audio_sample_rate),
        "-ac", str(config.audio_channels),
        "-movflags", "+faststart",
        str(output),
    ])
    subprocess.run(command, check=True, capture_output=True, text=True)


def shift_srt_for_packaging(
    path: Path,
    *,
    intro_seconds: float = 0.0,
    segment_durations: Optional[list[float]] = None,
    mid_seconds: float = 0.0,
) -> None:
    """Keep external subtitle cues aligned after intro and mid transitions."""
    if not path.is_file() or (intro_seconds <= 0 and mid_seconds <= 0):
        return
    boundaries = []
    elapsed = 0.0
    for duration in (segment_durations or [])[:-1]:
        elapsed += max(0.0, float(duration))
        boundaries.append(elapsed)
    timing = re.compile(
        r'^(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})(.*)$'
    )

    def seconds(value: str) -> float:
        hours, minutes, rest = value.split(':')
        secs, millis = rest.split(',')
        return int(hours) * 3600 + int(minutes) * 60 + int(secs) + int(millis) / 1000

    def timestamp(value: float) -> str:
        total_ms = max(0, round(value * 1000))
        hours, remainder = divmod(total_ms, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, millis = divmod(remainder, 1000)
        return f'{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}'

    shifted = []
    for line in path.read_text(encoding='utf-8').splitlines():
        match = timing.match(line)
        if not match:
            shifted.append(line)
            continue
        start = seconds(match.group(1))
        end = seconds(match.group(2))
        preceding_mid_count = sum(start >= boundary - 0.001 for boundary in boundaries)
        offset = intro_seconds + mid_seconds * preceding_mid_count
        shifted.append(f'{timestamp(start + offset)} --> {timestamp(end + offset)}{match.group(3)}')
    path.write_text('\n'.join(shifted) + '\n', encoding='utf-8')


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
    *,
    include_fades: bool = True,
) -> str:
    base = f"scale={config.video_width}:{config.video_height},format={config.video_pixel_format}"
    if not enable_motion or motion_style == "none":
        return base
    frames = max(1, round(duration * config.video_fps))
    fades = (
        "fade=t=in:st=0:d=0.35,"
        f"fade=t=out:st={max(0.0, duration - 0.45):.2f}:d=0.35,"
        if include_fades else ""
    )
    if motion_style == "pan":
        return (
            f"scale={round(config.video_width * 1.08)}:{round(config.video_height * 1.08)},"
            f"crop={config.video_width}:{config.video_height}:x='(iw-ow)*on/{frames}':y='(ih-oh)/2',"
            f"{fades}"
            f"format={config.video_pixel_format}"
        )
    return (
        "scale=iw*1.04:ih*1.04,"
        f"zoompan=z='min(1+0.04*on/{frames},1.04)':"
        "d=1:"
        f"s={config.video_width}x{config.video_height}:fps={config.video_fps},"
        f"{fades}"
        f"format={config.video_pixel_format}"
    )


def _music_frequencies(options: dict) -> tuple[str, str, str, str]:
    style = str(options.get("music_style") or "warm").strip().lower()
    if style == "bright":
        return ("262", "330", "392", "784")
    if style == "calm":
        return ("174", "220", "261", "523")
    if style == "tech":
        return ("220", "277", "370", "740")
    return ("196", "247", "294", "588")


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
    *,
    transition_seconds: float = 0.0,
) -> None:
    clips = [
        _ensure_audio_stream(ffmpeg, clip, output.parent, config)
        for clip in clips
    ]
    command = [ffmpeg, "-y"]
    for clip in clips:
        command.extend(["-i", str(clip)])
    transition = max(0.0, min(0.8, float(transition_seconds or 0.0)))
    durations = [_probe_media_duration(clip) for clip in clips]
    if transition > 0 and len(clips) > 1 and all(duration > 0 for duration in durations):
        transition = min(transition, min(durations) / 2)
        filters = []
        concat_parts = []
        for index in range(len(clips)):
            video_filters = [f"fps={config.video_fps}", "setpts=PTS-STARTPTS"]
            audio_filters = [
                f"aresample={config.audio_sample_rate}:async=1:first_pts=0",
                "asetpts=PTS-STARTPTS",
            ]
            if index > 0:
                video_filters.append(f"fade=t=in:st=0:d={transition:.3f}")
                audio_filters.append(f"afade=t=in:st=0:d={transition:.3f}")
            if index < len(clips) - 1:
                fade_out = max(0.0, durations[index] - transition)
                video_filters.append(
                    f"fade=t=out:st={fade_out:.3f}:d={transition:.3f}"
                )
                audio_filters.append(
                    f"afade=t=out:st={fade_out:.3f}:d={transition:.3f}"
                )
            filters.append(f"[{index}:v:0]{','.join(video_filters)}[v{index}]")
            filters.append(f"[{index}:a:0]{','.join(audio_filters)}[a{index}]")
            concat_parts.append(f"[v{index}][a{index}]")
        filters.append(
            "".join(concat_parts) + f"concat=n={len(clips)}:v=1:a=1[v][a]"
        )
        filter_complex = ";".join(filters)
    else:
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


def _probe_media_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return max(0.0, float(result.stdout.strip()))
    except (OSError, subprocess.CalledProcessError, TypeError, ValueError):
        return 0.0


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
