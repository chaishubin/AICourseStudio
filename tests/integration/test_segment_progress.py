"""Segment progress must reflect real FFmpeg time and stop short on failure."""
import shutil
import subprocess

import pytest

from vidppt.core.models import ProcessConfig
from vidppt.utils.course_packaging import _extract_video_range, _concat_with_ffmpeg
from vidppt.utils.ffmpeg_process import run_ffmpeg


@pytest.mark.integration
def test_real_ffmpeg_reports_intermediate_progress_and_keeps_output(tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('ffmpeg required')
    source = tmp_path / 'source.mp4'
    updates = []
    # Pace input so the encoder emits multiple progress reports on fast hosts.
    run_ffmpeg([ffmpeg, '-v', 'error', '-y', '-re', '-f', 'lavfi', '-i',
                'testsrc2=s=160x90:r=24:d=2', '-f', 'lavfi', '-i',
                'sine=frequency=440:duration=2', '-c:v', 'libx264',
                '-preset', 'ultrafast', '-c:a', 'aac', '-shortest', str(source)],
               duration=2, progress_callback=updates.append)
    assert any(0 < value < 1 for value in updates)
    assert updates == sorted(updates)
    assert updates[-1] == 1
    config = ProcessConfig(input_path=source, output_dir=tmp_path,
                           video_width=160, video_height=90)
    cut = tmp_path / 'cut.mp4'
    cut_updates = []
    _extract_video_range(ffmpeg, source, cut, config, start=0.25, duration=1,
                         progress_callback=cut_updates.append)
    assert cut_updates[-1] == 1
    assert cut.stat().st_size > 0
    joined_updates = []
    _concat_with_ffmpeg(ffmpeg, [cut, cut], tmp_path / 'joined.mp4', config,
                        transition_seconds=0.1, progress_callback=joined_updates.append)
    assert joined_updates[-1] == 1


@pytest.mark.integration
def test_failed_or_cancelled_ffmpeg_never_reports_complete(tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('ffmpeg required')
    updates = []
    with pytest.raises(subprocess.CalledProcessError):
        run_ffmpeg([ffmpeg, '-i', str(tmp_path / 'missing.mp4')],
                   duration=10, progress_callback=updates.append)
    assert 1 not in updates
    with pytest.raises(InterruptedError):
        run_ffmpeg([ffmpeg, '-re', '-f', 'lavfi', '-i', 'color=d=30', '-f', 'null', '-'],
                   lambda: True, duration=30, progress_callback=updates.append)
    assert 1 not in updates
