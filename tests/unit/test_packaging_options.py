"""Packaging switches must agree with rendering and progress reporting."""

from itertools import product

import pytest

from vidppt.core.models import ProcessConfig
from vidppt.utils import course_packaging


@pytest.mark.parametrize('intro,mid,outro', list(product([False, True], repeat=3)))
@pytest.mark.parametrize('durations', [None, [10], [10, 20]])
def test_active_parts_match_rendered_clips(tmp_path, monkeypatch, intro, mid, outro, durations):
    options = dict(enable_intro=intro, enable_mid=mid, enable_outro=outro,
                   transition_seconds=0)
    expected = (["intro"] if intro else []) + (["mid"] if mid and durations and len(durations) > 1 else []) + (["outro"] if outro else [])
    assert course_packaging.active_packaging_parts(options, durations) == expected
    rendered = []
    transitions = []
    source = tmp_path / 'body.mp4'
    source.write_bytes(b'body')
    output = tmp_path / 'output.mp4'
    config = ProcessConfig(input_path=tmp_path / 'source.pptx', output_dir=tmp_path)
    monkeypatch.setattr(course_packaging.shutil, 'which', lambda _: '/usr/bin/ffmpeg')

    def render(path, *_args, kind, **_kwargs):
        rendered.append(kind)
        path.write_bytes(b'clip')

    def extract(_ffmpeg, _source, path, *_args, **_kwargs):
        path.write_bytes(b'body')

    def concat(_ffmpeg, _clips, path, *_args, transition_seconds, **_kwargs):
        transitions.append(transition_seconds)
        path.write_bytes(b'packaged')

    monkeypatch.setattr(course_packaging, '_render_packaging_clip', render)
    monkeypatch.setattr(course_packaging, '_extract_video_range', extract)
    monkeypatch.setattr(course_packaging, '_concat_with_ffmpeg', concat)
    course_packaging.package_course_video(source, output, config, options,
                                         course_title='课程', segment_durations=durations)
    assert rendered == expected
    assert transitions == ([0] if expected else [])
    assert output.read_bytes() == (b'packaged' if expected else b'body')


def test_packaging_cache_invalidates_content_and_settings(tmp_path, monkeypatch):
    from dataclasses import replace
    asset = tmp_path / 'background.png'
    asset.write_bytes(b'first')
    config = ProcessConfig(input_path=tmp_path / 'source.pptx', output_dir=tmp_path)
    rendered = []

    def render(path, *_args, **_kwargs):
        rendered.append(path)
        path.write_bytes(f'clip{len(rendered)}'.encode())

    monkeypatch.setattr(course_packaging, '_render_packaging_clip', render)
    args = dict(kind='intro', course_title='课程', segment_title='',
                logo_path=None, background_path=asset)
    output = tmp_path / 'intro.mp4'
    options = {'enable_music': False}
    course_packaging._cached_packaging_clip(output, config, options, **args)
    output.write_bytes(b'changed downstream')
    course_packaging._cached_packaging_clip(output, config, options, **args)
    assert len(rendered) == 1 and output.read_bytes() == b'clip1'
    asset.write_bytes(b'other')
    course_packaging._cached_packaging_clip(output, config, options, **args)
    assert len(rendered) == 2
    course_packaging._cached_packaging_clip(output, replace(config, video_fps=30), options, **args)
    course_packaging._cached_packaging_clip(output, config, options, **{**args, 'course_title': '新课程'})
    course_packaging._cached_packaging_clip(output, config, {'enable_music': True}, **args)
    assert len(rendered) == 5


def test_failed_clip_render_does_not_publish_cache(tmp_path, monkeypatch):
    config = ProcessConfig(input_path=tmp_path / 'source.pptx', output_dir=tmp_path)

    def fail(path, *_args, **_kwargs):
        path.write_bytes(b'incomplete')
        raise InterruptedError('stopped')

    monkeypatch.setattr(course_packaging, '_render_packaging_clip', fail)
    with pytest.raises(InterruptedError):
        course_packaging._cached_packaging_clip(tmp_path / 'clip.mp4', config, {},
            kind='intro', course_title='课程', segment_title='', logo_path=None, background_path=None)
    assert not list((tmp_path / '.packaging_cache').glob('*.mp4'))


def test_copy_concat_rejects_shifted_output_and_cleans_up(tmp_path, monkeypatch):
    source, output = tmp_path / 'source.mp4', tmp_path / 'output.mp4'
    source.write_bytes(b'body')
    commands = []
    monkeypatch.setattr(course_packaging, '_stream_signature', lambda _, **_kwargs: (('same',), {'video': (0, 1), 'audio': (0, 1)}))
    monkeypatch.setattr(course_packaging, '_stream_timing', lambda path: {
        'video': (0.021 if path == output else 0, 2 if path == output else 1),
        'audio': (0, 2 if path == output else 1),
    })

    def run(command, _cancel):
        commands.append(command)
        output.write_bytes(b'bad timing')

    monkeypatch.setattr(course_packaging, 'run_ffmpeg', run)
    assert not course_packaging._try_copy_concat('/usr/bin/ffmpeg', [source, source], output)
    assert not output.exists()
    assert commands[0][commands[0].index('-c:v') + 1] == 'copy'
    assert commands[0][commands[0].index('-c:a') + 1] == 'aac'


def test_copy_concat_rejects_incompatible_streams_before_encoding(tmp_path, monkeypatch):
    first, second = tmp_path / 'first.mp4', tmp_path / 'second.mp4'
    monkeypatch.setattr(course_packaging, '_stream_signature', lambda path, **_kwargs: (str(path), None))
    monkeypatch.setattr(course_packaging, 'run_ffmpeg', lambda *_args: pytest.fail('must fall back'))
    assert not course_packaging._try_copy_concat('/usr/bin/ffmpeg', [first, second], tmp_path / 'out.mp4')
