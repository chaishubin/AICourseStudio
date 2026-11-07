"""Concurrency, cancellation, cache invalidation and background result ownership."""
import asyncio
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from types import SimpleNamespace

import pytest
from PIL import Image

from vidppt.core.interfaces import TTSEngine
from vidppt.core.models import PageContent
from vidppt.generation.page_analysis import generate_presentation_narration
from vidppt.utils.performance import timed_step
from vidppt.utils.render_capacity import render_capacity
from vidppt.utils.ffmpeg_process import run_ffmpeg


@pytest.mark.asyncio
async def test_tts_fills_vacant_slots_without_waiting_for_slowest_request(tmp_path):
    release_first, third_started = asyncio.Event(), asyncio.Event()
    active = peak = 0
    progress = []

    class Engine(TTSEngine):
        async def convert_async(self, text, output_path, voice, rate):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                if text == '1':
                    await release_first.wait()
                if text == '3':
                    third_started.set()
                await asyncio.sleep(0)
            finally:
                active -= 1

    job = asyncio.create_task(Engine().batch_convert(
        [(i, str(i), tmp_path / f'{i}.mp3') for i in range(1, 5)], 'voice', '+0%',
        batch_size=2, progress_callback=lambda current, *_: progress.append(current),
    ))
    try:
        await asyncio.wait_for(third_started.wait(), 2)
    finally:
        release_first.set()
        await job
    assert peak == 2
    assert progress == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_tts_cancellation_stops_dispatching_queued_requests(tmp_path):
    stopped = False
    calls = []

    class Engine(TTSEngine):
        async def convert_async(self, text, output_path, voice, rate):
            nonlocal stopped
            calls.append(text)
            stopped = True

    with pytest.raises(InterruptedError):
        await Engine().batch_convert(
            [(i, str(i), tmp_path / f'{i}.mp3') for i in range(3)], 'v', '+0%',
            batch_size=1, cancel_check=lambda: stopped,
        )
    assert calls == ['0']


def test_parallel_page_analysis_keeps_narration_in_order_and_reuses_cache(tmp_path):
    barrier = threading.Barrier(3, timeout=3)
    calls = []
    contexts = []

    class Engine:
        model, api_url, options = 'test', 'https://example.invalid', {}

        def analyze_slide(self, source, image, **kwargs):
            calls.append(image.name)
            barrier.wait()
            return json.dumps({'summary': image.stem, 'objects': [], 'uncertainties': []})

        def summarize(self, text, **kwargs):
            context = json.loads(text)
            contexts.append(context)
            script = f"page {context['current_page']}"
            return json.dumps({'script': script, 'focus_cues': [{'text': script, 'action': 'clear'}]})

    def pages():
        result = []
        for i in range(1, 4):
            image = tmp_path / f'slide{i}.png'
            Image.new('RGB', (40, 30), 'white').save(image)
            result.append(PageContent(page_number=i, text=f'source {i}', slide_image=image))
        return result

    engine = Engine()
    first = pages()
    generate_presentation_narration(engine, first, [], tmp_path, analysis_workers=3)
    assert [p.text for p in first] == ['page 1', 'page 2', 'page 3']
    assert [c['previous_script'] for c in contexts] == ['', 'page 1', 'page 2']
    generate_presentation_narration(engine, pages(), [], tmp_path, analysis_workers=3)
    assert len(calls) == len(contexts) == 3
    generate_presentation_narration(engine, pages(), [], tmp_path, instructions='new wording')
    assert len(calls) == 3 and len(contexts) == 6


def test_timing_reports_are_atomic_and_count_failures(tmp_path):
    def measured(_):
        with timed_step(tmp_path, 'request'):
            pass
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(measured, range(20)))
    with pytest.raises(ValueError):
        with timed_step(tmp_path, 'request'):
            raise ValueError('failed')
    step = json.loads((tmp_path / 'performance.json').read_text())['steps']['request']
    assert step['calls'] == 21 and step['failures'] == 1


def test_render_capacity_cancels_waiter_without_interrupting_owner():
    entered, release, waiting = threading.Event(), threading.Event(), threading.Event()
    cancel = threading.Event()

    def owner():
        with render_capacity():
            entered.set()
            assert release.wait(3)

    def waiter():
        waiting.set()
        with render_capacity(cancel.is_set):
            raise AssertionError('cancelled waiter must not render')

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(owner)
        assert entered.wait(2)
        second = pool.submit(waiter)
        try:
            assert waiting.wait(2)
            cancel.set()
            with pytest.raises(InterruptedError):
                second.result(timeout=2)
        finally:
            release.set()
            first.result(timeout=2)
    with render_capacity():
        pass


def test_ffmpeg_process_drains_large_stderr_and_can_cancel():
    run_ffmpeg([sys.executable, '-c', 'import sys; sys.stderr.write("x" * 1000000)'])
    with pytest.raises(InterruptedError):
        run_ffmpeg([sys.executable, '-c', 'import time; time.sleep(30)'], lambda: True)


def setup_review(monkeypatch, tmp_path):
    import web.app as app
    (tmp_path / 'preview.json').write_text(json.dumps({'pages': [{'page_number': 1, 'script': 'original'}]}))
    monkeypatch.setattr(app, 'tasks', {'review': {'status': 'processing', 'output_dir': str(tmp_path),
                                               'strategy': {'quality_mode': 'premium'}}})
    monkeypatch.setattr(app, 'save_state', lambda _: None)
    scheduled = []
    monkeypatch.setattr(app, '_review_executor', SimpleNamespace(submit=lambda f: scheduled.append(f)))
    monkeypatch.setattr(app, 'CourseReviewer', lambda: SimpleNamespace(review=lambda *_: {
        'status': 'passed', 'review_completed': True, 'summary': 'finished', 'findings': [],
    }))
    return app, scheduled


def test_auto_review_returns_before_running_and_does_not_replace_media_status(monkeypatch, tmp_path):
    app, scheduled = setup_review(monkeypatch, tmp_path)
    app._auto_review_preview('review')
    assert app._read_preview('review')['ai_review']['running'] is True
    assert len(scheduled) == 1
    app.tasks['review']['message'] = 'encoding'
    scheduled[0]()
    assert app.tasks['review']['message'] == 'encoding'
    assert app._read_preview('review')['ai_review']['review_completed'] is True


def test_obsolete_background_review_cannot_overwrite_newer_result(monkeypatch, tmp_path):
    app, scheduled = setup_review(monkeypatch, tmp_path)
    app._auto_review_preview('review')
    newest = app._run_course_review('review', 'sample')
    scheduled[0]()
    assert app._read_preview('review')['ai_review'] == newest


def test_review_is_marked_stale_when_scripts_change_during_request(monkeypatch, tmp_path):
    app, scheduled = setup_review(monkeypatch, tmp_path)

    def review(*_):
        preview = app._read_preview('review')
        preview['pages'][0]['script'] = 'edited'
        app._persist_preview('review', preview)
        return {'status': 'passed', 'review_completed': True}

    monkeypatch.setattr(app, 'CourseReviewer', lambda: SimpleNamespace(review=review))
    app._auto_review_preview('review')
    scheduled[0]()
    assert app._read_preview('review')['pages'][0]['script'] == 'edited'
    assert app._read_preview('review')['ai_review']['stale'] is True


def test_queue_overlaps_network_jobs(monkeypatch):
    import web.app as app
    monkeypatch.setenv('CONVERSION_WORKERS', '2')
    monkeypatch.setattr(app, 'tasks', {name: {'status': 'queued'} for name in ('one', 'two')})
    monkeypatch.setattr(app, 'cancellation_events', {})
    barrier = threading.Barrier(2, timeout=3)
    finished = Queue()
    queue = app.ConversionQueue()
    monkeypatch.setattr(queue, '_wait_for_capacity', lambda *_: True)

    def job(name):
        try:
            barrier.wait()
            app.tasks[name]['status'] = 'completed'
            finished.put(name)
        except BaseException as exc:
            finished.put(exc)

    for name in ('one', 'two'):
        queue.enqueue(job, name)
    assert {finished.get(timeout=4), finished.get(timeout=4)} == {'one', 'two'}


def test_stage_timer_accumulates_repeated_video_stages(monkeypatch, tmp_path):
    import web.app as app
    monkeypatch.setattr(app, 'tasks', {'timing': {}})
    monkeypatch.setattr(app, 'save_state', lambda _: None)
    tracker = app.WebProgressTracker('timing', Queue())
    monkeypatch.setattr(app.time, 'time', lambda: 100)
    tracker.set_stage('video')
    monkeypatch.setattr(app.time, 'time', lambda: 110)
    tracker.set_stage('video')
    monkeypatch.setattr(app.time, 'time', lambda: 115)
    tracker._complete_current_stage()
    tracker._complete_current_stage()
    assert app.tasks['timing']['stage_timings']['video']['duration'] == 15


def test_performance_endpoint_returns_timing_reports(monkeypatch, tmp_path):
    import web.app as app
    monkeypatch.setattr(app, 'tasks', {'timing': {'output_dir': str(tmp_path)}})
    with timed_step(tmp_path, 'request'):
        pass
    response = app.app.test_client().get('/api/task-performance/timing')
    assert response.status_code == 200
    assert response.get_json()['reports']['performance.json']['steps']['request']['calls'] == 1
    assert app.app.test_client().get('/api/task-performance/missing').status_code == 404


def test_restart_clears_abandoned_background_review(monkeypatch, tmp_path):
    import web.app as app
    preview = tmp_path / 'preview.json'
    review = {'running': True, 'status': 'pending'}
    preview.write_text(json.dumps({'pages': [], 'ai_review': review}))
    entry = {'task_id': 'restarted', 'status': 'awaiting_confirmation',
             'preview_path': str(preview), 'ai_review': review}
    monkeypatch.setattr(app, 'STATE_FILE', tmp_path / 'state.json')
    monkeypatch.setattr(app, 'DEFAULT_STATE_FILE', tmp_path / 'unused.json')
    monkeypatch.setattr(app, '_read_state_file', lambda: [entry])
    monkeypatch.setattr(app, 'tasks', {})
    app.load_state()
    assert app.tasks['restarted']['ai_review']['running'] is False
    assert json.loads(preview.read_text())['ai_review']['running'] is False
