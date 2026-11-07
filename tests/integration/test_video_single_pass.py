"""Exercise the real encoder to catch subtitle/filter/audio regressions."""
import shutil
import wave
from dataclasses import replace

import numpy as np
import pytest
from PIL import Image
from moviepy import VideoFileClip

from vidppt.core.models import DocumentContent, PageContent, ProcessConfig
from vidppt.course_pipeline import CoursePipeline
from vidppt.utils.video_composer import VideoComposer
from vidppt.utils.course_packaging import _extract_video_range, _try_copy_concat


@pytest.mark.integration
def test_single_pass_matches_two_pass_subtitles_and_audio(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is required")
    folder = tmp_path / "课程's [draft]"
    folder.mkdir()
    slide = folder / "slide.png"
    Image.new("RGB", (480, 270), (50, 90, 130)).save(slide)
    audio = folder / "voice.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(48000)
        samples = (np.sin(np.arange(96000) * 2 * np.pi * 440 / 48000) * 3000).astype("<i2")
        stream.writeframes(samples.tobytes())
    subtitles = folder / "字幕's.srt"
    subtitles.write_text("1\n00:00:00,200 --> 00:00:01,200\nSingle pass subtitle\n", encoding="utf-8")
    config = ProcessConfig(input_path=slide, output_dir=folder, video_width=480, video_height=270)
    second_slide = folder / "second.png"
    Image.new("RGB", (240, 270), (100, 60, 130)).save(second_slide)
    content = DocumentContent(pages=[
        PageContent(page_number=1, text="test", slide_image=slide, audio=audio),
        PageContent(page_number=2, text="focus", slide_image=second_slide, audio=audio, metadata={
            "focus_targets": [{"id": "point", "x": 0.1, "y": 0.2, "width": 0.4, "height": 0.1}],
            "focus_cues": [{"text": "focus", "target_id": "point", "weight": 1}],
        }),
    ])
    base, old, new = [folder / name for name in ("base.mp4", "old.mp4", "new.mp4")]
    VideoComposer.compose(content, config, base)
    # The legacy filter cannot handle apostrophes in the subtitle filename.
    reference_subtitles = folder / "reference.srt"
    shutil.copyfile(subtitles, reference_subtitles)
    CoursePipeline._burn_subtitles(base, reference_subtitles, old, config)
    progress = []
    VideoComposer.compose(content, config, new, subtitles=subtitles, progress_callback=progress.append)
    with VideoFileClip(str(base)) as plain, VideoFileClip(str(old)) as previous, VideoFileClip(str(new)) as current:
        assert current.size == [480, 270]
        assert abs(current.duration - previous.duration) < 0.1
        assert current.audio is not None
        assert np.max(np.abs(current.audio.get_frame(0.5))) > 0.001
        for time in (0.5, 1.5, 2.5, 3.5):
            delta = np.abs(current.get_frame(time).astype(float) - previous.get_frame(time))
            assert delta.mean() < 3
        # Verify actual text pixels, beyond the always-present subtitle backdrop.
        lit = current.get_frame(0.5)[225:260].astype(float)
        unlit = current.get_frame(1.5)[225:260].astype(float)
        assert np.count_nonzero(np.max(np.abs(lit - unlit), axis=2) > 50) > 40
        # The page boundary, letterboxing and animated focus layer survive chain concatenation.
        second_frame = current.get_frame(2.5)
        assert second_frame[100, 10].max() < 10
        assert np.count_nonzero(
            (second_frame[:150, :, 0] > 190)
            & (second_frame[:150, :, 1] > 130)
            & (second_frame[:150, :, 2] < 190)
        ) > 30
    assert progress and progress[-1] > 0.9
    # Disabling burned subtitles must not even read the optional subtitle file.
    disabled = folder / "disabled.mp4"
    VideoComposer.compose(
        content, replace(config, burn_subtitles=False), disabled,
        subtitles=folder / "missing.srt",
    )
    with VideoFileClip(str(base)) as plain, VideoFileClip(str(disabled)) as current:
        assert np.abs(plain.get_frame(0.5).astype(float) - current.get_frame(0.5)).mean() < 1
    # Cut the rendered body at a non-keyframe boundary; preserve subtitles,
    # focus and audio without running the Python compositor again.
    first_cut, second_cut = folder / 'cut1.mp4', folder / 'cut2.mp4'
    for output, start, duration in ((first_cut, 0, 1.75), (second_cut, 1.75, 2.25)):
        _extract_video_range(shutil.which('ffmpeg'), new, output, config, start=start, duration=duration)
    with VideoFileClip(str(new)) as original, VideoFileClip(str(second_cut)) as cut:
        assert abs(cut.duration - 2.25) < 0.1
        assert cut.audio is not None
        assert np.abs(original.get_frame(2.5).astype(float) - cut.get_frame(0.75)).mean() < 3
    joined = folder / 'joined.mp4'
    assert _try_copy_concat(shutil.which('ffmpeg'), [first_cut, second_cut], joined)
    with VideoFileClip(str(joined)) as result:
        assert abs(result.duration - 4) < 0.15
        assert result.audio is not None
        assert np.abs(result.get_frame(2.5).astype(float) - second_frame).mean() < 3
