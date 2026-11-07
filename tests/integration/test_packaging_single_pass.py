"""Real FFmpeg regression and repeatable old/new packaging benchmark."""
import json
import shutil
import subprocess
from time import perf_counter

import numpy as np
import pytest
from moviepy import VideoFileClip

from vidppt.core.models import ProcessConfig
from vidppt.utils.course_packaging import _concat_with_ffmpeg, _extract_video_range


def encode(ffmpeg, path, duration, *, body=False, size=(960, 540)):
    dimensions = f'{size[0]}x{size[1]}'
    video = f'testsrc2=s={dimensions}:r=24:d={duration}' if body else f'color=c=navy:s={dimensions}:r=24:d={duration}'
    # Audible markers every second expose missing samples and timeline drift.
    audio = f"aevalsrc=0.15*sin(2*PI*440*t)*lt(mod(t\\,1)\\,0.15):s=48000:d={duration}"
    command = [ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i', video,
               '-f', 'lavfi', '-i', audio]
    if body:
        subtitles = path.with_suffix('.srt')
        subtitles.write_text('1\n00:00:01,000 --> 00:00:02,000\nSync subtitle one\n\n'
                             '2\n00:00:05,000 --> 00:00:06,000\nSync subtitle two\n\n'
                             '3\n00:00:09,000 --> 00:00:10,000\nSync subtitle three\n', encoding='utf-8')
        command += ['-vf', f"subtitles=filename='{subtitles}',drawbox=x=100:y=460:w=760:h=45:color=white:t=fill:enable='between(t,1,2)+between(t,5,6)+between(t,9,10)'"]
    command += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
                '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-g', '48',
                '-c:a', 'aac', '-b:a', '128k', '-ac', '1', '-ar', '48000', str(path)]
    subprocess.run(command, check=True, capture_output=True)


@pytest.mark.integration
@pytest.mark.parametrize('transition,size', [(0, (960, 540)), (0.35, (960, 540)), (0.35, (1920, 1080))])
def test_packaging_ranges_match_legacy_and_measure_speed(tmp_path, transition, size):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('ffmpeg required')
    config = ProcessConfig(input_path=tmp_path / 'source.pptx', output_dir=tmp_path,
                           video_width=size[0], video_height=size[1])
    body, card = tmp_path / 'body.mp4', tmp_path / 'card.mp4'
    encode(ffmpeg, body, 12, body=True, size=size)
    encode(ffmpeg, card, 1, size=size)
    legacy, current = tmp_path / 'legacy.mp4', tmp_path / 'current.mp4'
    # Exact frame boundary, deliberately away from a keyframe.
    boundary = 4.25
    elapsed = {'legacy': [], 'single_pass': []}
    for repeat in range(2):
        # Alternate order to reduce warm-cache and thermal bias.
        for mode in (('legacy', 'single_pass') if repeat == 0 else ('single_pass', 'legacy')):
            started = perf_counter()
            if mode == 'legacy':
                first, second = tmp_path / 'first.mp4', tmp_path / 'second.mp4'
                _extract_video_range(ffmpeg, body, first, config, start=0, duration=boundary)
                _extract_video_range(ffmpeg, body, second, config, start=boundary, duration=None)
                clips, ranges, output = [card, first, card, second, card], {}, legacy
            else:
                clips, ranges, output = [card, body, card, body, card], {1: (0, boundary), 3: (boundary, None)}, current
            _concat_with_ffmpeg(ffmpeg, clips, output, config, transition_seconds=transition,
                                clip_ranges=ranges)
            elapsed[mode].append(perf_counter() - started)
    errors = []
    with VideoFileClip(str(legacy)) as old, VideoFileClip(str(current)) as new:
        assert new.size == old.size == list(size)
        assert abs(new.duration - 15) < 0.08
        assert abs(new.duration - old.duration) < 0.08
        for t in [0.5, 1.1, 2.5, 4.9, 5.2, 5.4, 6.4, 7, 10.5, 13.8, 14.5]:
            error = np.abs(new.get_frame(t).astype(float) - old.get_frame(t)).mean()
            errors.append(float(error))
            assert error < 6, (t, error)
        # Burned subtitle marker remains on at its shifted time and off later.
        assert new.get_frame(2.5)[475:490, 120:840].mean() > 230
        assert new.get_frame(3.5)[475:490, 120:840].mean() < 220
    def pcm(path):
        return np.frombuffer(subprocess.run([ffmpeg, '-v', 'error', '-i', str(path),
            '-vn', '-f', 'f32le', '-ac', '1', '-ar', '48000', '-'],
            check=True, capture_output=True).stdout, dtype='<f4')
    old_audio, new_audio = pcm(legacy), pcm(current)
    assert abs(len(old_audio) - len(new_audio)) / 48000 < 0.08
    # Envelope of each marker must stay aligned, including after the mid card.
    lags = []
    absolute_lags = []
    for t in [2, 3, 7, 8, 11, 13]:
        start, end = int((t - 0.1) * 48000), int((t + 0.3) * 48000)
        old_window, new_window = old_audio[start:end], new_audio[start:end]
        old_peak = np.flatnonzero(np.abs(old_window) > 0.06)[0]
        new_peak = np.flatnonzero(np.abs(new_window) > 0.06)[0]
        lags.append(abs(int(old_peak) - int(new_peak)) / 48000)
        absolute_lags.append(abs((start + int(new_peak)) / 48000 - t))
    assert max(lags) < 0.025, lags
    assert max(absolute_lags) < 0.01, absolute_lags
    previous, optimized = (float(np.median(elapsed[key])) for key in ('legacy', 'single_pass'))
    report = dict(transition=transition, seconds=elapsed, speedup=previous / optimized,
                  max_frame_error=max(errors), max_audio_lag_seconds=max(lags), max_absolute_audio_lag_seconds=max(absolute_lags),
                  resolution=f'{size[0]}x{size[1]}', body_seconds=12)
    (tmp_path / 'benchmark.json').write_text(json.dumps(report, indent=2))
    print('\nPACKAGING_BENCHMARK ' + json.dumps(report))


@pytest.mark.integration
def test_segment_intro_is_single_encode_and_cache_reused(tmp_path):
    from vidppt.utils import course_packaging as packaging
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('ffmpeg required')
    config = ProcessConfig(input_path=tmp_path / 'source.pptx', output_dir=tmp_path,
                           video_width=960, video_height=540)
    body = tmp_path / 'body.mp4'
    encode(ffmpeg, body, 12, body=True)
    options = dict(enable_intro=True, enable_outro=False, enable_motion=False,
                   enable_music=False, intro_duration_seconds=1, template='minimal',
                   transition_seconds=0.35)
    first, second = tmp_path / 'first.mp4', tmp_path / 'second.mp4'
    packaging.package_course_video(body, first, config, options, course_title='Sync test',
                                   source_range=(4.25, 3))
    timing = json.loads((tmp_path / 'performance.json').read_text())['steps']
    assert 'video_range_encode' not in timing
    assert timing['packaging_clip_render']['calls'] == 1
    packaging.package_course_video(body, second, config, options, course_title='Sync test',
                                   source_range=(4.25, 3))
    timing = json.loads((tmp_path / 'performance.json').read_text())['steps']
    assert timing['packaging_clip_render']['calls'] == 1
    assert timing['packaging_filter_encode']['calls'] == 2
    with VideoFileClip(str(body)) as source, VideoFileClip(str(second)) as result:
        assert abs(result.duration - 4) < 0.05
        assert result.audio is not None
        assert np.abs(source.get_frame(5.75).astype(float) - result.get_frame(2.5)).mean() < 3
    # A canceled run must leave the previously published output intact.
    previous = second.read_bytes()
    with pytest.raises(InterruptedError):
        packaging.package_course_video(body, second, config, options, course_title='Sync test',
                                       source_range=(4.25, 3), cancel_check=lambda: True)
    assert second.read_bytes() == previous


@pytest.mark.integration
def test_copy_video_concat_matches_encoded_timeline_and_measure_speed(tmp_path):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('ffmpeg required')
    config = ProcessConfig(input_path=tmp_path / 'source.pptx', output_dir=tmp_path,
                           video_width=960, video_height=540)
    body, card = tmp_path / 'body.mp4', tmp_path / 'card.mp4'
    encode(ffmpeg, body, 12, body=True)
    encode(ffmpeg, card, 1)
    encoded, copied = tmp_path / 'encoded.mp4', tmp_path / 'copied.mp4'
    elapsed = {'encoded': [], 'video_copy': []}
    for repeat in range(2):
        for mode in (('encoded', 'video_copy') if repeat == 0 else ('video_copy', 'encoded')):
            started = perf_counter()
            _concat_with_ffmpeg(ffmpeg, [card, body, card], copied if mode == 'video_copy' else encoded,
                                config, clip_ranges={} if mode == 'video_copy' else {1: (0, None)})
            elapsed[mode].append(perf_counter() - started)
    timing = json.loads((tmp_path / 'performance.json').read_text())['steps']
    assert timing['packaging_copy_concat']['calls'] == 2
    assert timing['packaging_filter_encode']['calls'] == 2  # no unexpected fallback
    with VideoFileClip(str(body)) as original, VideoFileClip(str(copied)) as fast, VideoFileClip(str(encoded)) as slow:
        assert abs(fast.duration - 14) < 0.03
        for t in [0.5, 2.5, 5.5, 10.5]:
            assert np.abs(original.get_frame(t).astype(float) - fast.get_frame(t + 1)).mean() == 0
            assert np.abs(slow.get_frame(t + 1).astype(float) - fast.get_frame(t + 1)).mean() < 3
    from vidppt.utils.course_packaging import _stream_timing
    actual = _stream_timing(copied)
    assert all(abs(actual[kind][0]) < 0.001 for kind in ('video', 'audio'))
    report = dict(scenario='compatible_video_copy', seconds=elapsed,
                  speedup=float(np.median(elapsed['encoded']) / np.median(elapsed['video_copy'])))
    (tmp_path / 'benchmark.json').write_text(json.dumps(report, indent=2))
    print('\nPACKAGING_BENCHMARK ' + json.dumps(report))
