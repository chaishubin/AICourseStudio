import json

import pytest

from vidppt.core.course import Course, CourseSection


@pytest.fixture
def preview_task(monkeypatch, tmp_path):
    import web.app as web_app

    pages = [{
        'page_number': number, 'title': f'内容{number}', 'script': '原讲稿。',
        'duration': 40, 'audio_signature': 'old', 'image_path': str(tmp_path / 'slide.png'),
        'focus_targets': [{'id': 'box', 'text': '课程内容'}],
        'focus_cues': [{'text': '原讲稿。', 'start': 0, 'end': 40,
                        'timing_source': 'segment_audio', 'subtitle_unit': True}],
    } for number in range(1, 4)]
    settings = {'target_minutes': 1, 'priority': 'duration'}
    segments = web_app._recommend_lesson_segments(pages, **settings)
    course_path = tmp_path / 'course.json'
    course = Course(title='测试', sections=[CourseSection(id=str(n), title=f'内容{n}', script='原讲稿。') for n in range(1, 4)])
    course_path.write_text(json.dumps(course.to_dict()), encoding='utf-8')
    preview = {'pages': pages, 'lesson_segments': segments,
               'segmentation_settings': settings, 'course_json_path': str(course_path)}
    path = tmp_path / 'preview.json'
    path.write_text(json.dumps(preview), encoding='utf-8')
    for number in range(1, 4):
        (tmp_path / str(number)).mkdir()
        (tmp_path / str(number) / 'audio.mp3').write_bytes(b'old-audio')
    monkeypatch.setattr(web_app, 'tasks', {'sync-task': {
        'status': 'awaiting_confirmation', 'output_dir': str(tmp_path),
    }})
    return web_app, path, course_path


def test_fix_refreshes_focus_duration_applied_auto_cuts_and_course(preview_task):
    app, path, course_path = preview_task
    replacement = '新' * 300 + '。'
    response = app.app.test_client().patch('/api/course-preview/sync-task', json={
        'pages': [{'page_number': 1, 'script': replacement}],
    })
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['changed_pages'] == [1]
    page = payload['pages'][0]
    assert page['script'] == replacement
    assert app._focus_cues_cover_script(page['focus_cues'], replacement)
    assert all('start' not in cue and 'end' not in cue for cue in page['focus_cues'])
    assert page['estimated_seconds'] > 60
    assert [(item['start_page'], item['end_page']) for item in payload['lesson_segments']] == [(1, 1), (2, 3)]
    assert payload['pages'][1]['lesson_segment']['id'] == 2
    saved = json.loads(path.read_text())
    assert 'audio_signature' not in saved['pages'][0]
    assert 'duration' not in saved['pages'][0]
    assert not (path.parent / '1/audio.mp3').exists()
    assert (path.parent / '2/audio.mp3').read_bytes() == b'old-audio'
    course = json.loads(course_path.read_text())
    assert course['sections'][0]['script'] == replacement
    assert course['metadata']['lesson_segments'] == payload['lesson_segments']
    assert saved['duration_estimate'] == payload['duration_estimate']


def test_manual_cuts_keep_ranges_and_refresh_duration(preview_task):
    app, path, _ = preview_task
    preview = json.loads(path.read_text())
    preview['segmentation_settings'] = None
    path.write_text(json.dumps(preview))
    response = app.app.test_client().patch('/api/course-preview/sync-task', json={
        'pages': [{'page_number': 1, 'script': '新' * 300}],
    })
    segments = response.get_json()['lesson_segments']
    assert [(s['start_page'], s['end_page']) for s in segments] == [(1, 2), (3, 3)]
    assert segments[0]['estimated_seconds'] > 100


def test_draft_recommendations_refresh_without_overwriting_applied_cuts(preview_task):
    app, path, _ = preview_task
    preview = json.loads(path.read_text())
    preview['segmentation_settings'] = None
    path.write_text(json.dumps(preview))
    response = app.app.test_client().patch('/api/course-preview/sync-task', json={
        'pages': [{'page_number': 1, 'script': '新' * 300}],
        'recommendation_options': {'target_minutes': 1, 'priority': 'duration'},
    })
    data = response.get_json()
    assert data['lesson_segments'][0]['end_page'] == 2
    assert data['recommended_segments'][0]['end_page'] == 1


def test_apply_records_auto_settings_but_manual_titles_disable_auto_recut(preview_task):
    app, path, _ = preview_task
    client = app.app.test_client()
    settings = {'target_minutes': 1, 'priority': 'duration'}
    segments = json.loads(path.read_text())['lesson_segments']
    response = client.post('/api/course-segments/sync-task', json={
        'segments': segments, 'recommendation_options': settings,
    })
    assert response.status_code == 200
    assert json.loads(path.read_text())['segmentation_settings'] == settings
    segments[0]['title'] = '手工命名'
    response = client.post('/api/course-segments/sync-task', json={
        'segments': segments, 'recommendation_options': settings,
    })
    assert response.status_code == 200
    assert json.loads(path.read_text())['segmentation_settings'] is None


def test_invalid_cut_settings_do_not_save_script(preview_task):
    app, path, _ = preview_task
    before = path.read_bytes()
    response = app.app.test_client().patch('/api/course-preview/sync-task', json={
        'pages': [{'page_number': 1, 'script': '不应保存'}],
        'recommendation_options': {'target_minutes': None},
    })
    assert response.status_code == 400
    assert path.read_bytes() == before


def test_page_focus_mode_roundtrips_without_erasing_calibration(preview_task):
    app, path, course_path = preview_task
    preview = json.loads(path.read_text())
    page = preview['pages'][0]
    page['focus_cues'][0].update(start=0, end=4, target_id='box', subtitle_unit=True)
    manual = {'start': 1, 'end': 2, 'target_ids': [], 'manual': True}
    page['focus_events'] = [manual]
    path.write_text(json.dumps(preview))
    client = app.app.test_client()
    for mode in ['off', 'manual', 'auto']:
        result = client.patch('/api/course-preview/sync-task', json={
            'pages': [{'page_number': 1, 'script': '原讲稿。', 'focus_mode': mode}]
        })
        assert result.status_code == 200
        saved = result.get_json()['pages'][0]
        assert saved['focus_mode'] == mode
        assert any(e.get('manual') and e['target_ids'] == [] for e in saved['focus_events'])
        assert json.loads(course_path.read_text())['sections'][0]['metadata']['focus_mode'] == mode


def test_resetting_cue_to_auto_does_not_retain_a_stale_clear_interval(preview_task):
    app, path, _ = preview_task
    preview = json.loads(path.read_text())
    page = preview['pages'][0]
    page['script'] = '课程内容。'
    page['focus_cues'] = [{'text': '课程内容。', 'start': 0, 'end': 4, 'subtitle_unit': True,
                           'target_id': '', 'manual': True}]
    page['focus_events'] = [{'start': 0, 'end': 4, 'target_ids': [], 'manual': True}]
    path.write_text(json.dumps(preview))
    result = app.app.test_client().patch('/api/course-preview/sync-task', json={
        'pages': [{'page_number': 1, 'script': '课程内容。',
                   'focus_cues': [{'text': '课程内容。', 'start': 0, 'end': 4, 'subtitle_unit': True,
                                   'manual': False, 'source': 'fallback', 'target_id': ''}],
                   'focus_events': [], 'focus_events_manual_clear': False}]
    })
    assert result.status_code == 200
    page = result.get_json()['pages'][0]
    assert page['focus_cues'][0]['target_id'] == 'box'
    assert page['focus_events'][0]['target_ids'] == ['box']
    assert page['focus_events_manual_clear'] is False


def test_invalid_focus_mode_is_rejected(preview_task):
    app, _, _ = preview_task
    result = app.app.test_client().patch('/api/course-preview/sync-task', json={
        'pages': [{'page_number': 1, 'focus_mode': 'invalid'}]
    })
    assert result.status_code == 400
