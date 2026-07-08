"""Web 登录与访问保护测试。"""

import pytest


@pytest.fixture
def auth_client(monkeypatch):
    import web.app as app_module

    monkeypatch.setattr(app_module, 'AUTH_USERNAME', 'tester')
    monkeypatch.setattr(app_module, 'AUTH_PASSWORD', 'correct-password')
    monkeypatch.setattr(app_module, 'ACCOUNTS', {
        'tester': {
            'password': 'correct-password',
            'role': 'super_admin',
            'display_name': 'tester',
        }
    })
    monkeypatch.setitem(app_module.app.config, 'TESTING', True)
    monkeypatch.setitem(app_module.app.config, 'SECRET_KEY', 'test-secret')
    monkeypatch.setitem(app_module.app.config, 'LOGIN_DISABLED', False)
    return app_module.app.test_client()


def test_page_redirects_to_login(auth_client):
    response = auth_client.get('/')
    assert response.status_code == 302
    assert response.headers['Location'].startswith('/login')


def test_api_returns_401_when_unauthenticated(auth_client):
    response = auth_client.get('/api/tasks')
    assert response.status_code == 401
    assert response.get_json()['code'] == 'authentication_required'


def test_login_rejects_wrong_password(auth_client):
    response = auth_client.post('/login', data={
        'username': 'tester',
        'password': 'wrong',
    })
    assert response.status_code == 200
    assert '用户名或密码错误'.encode() in response.data


def test_login_allows_workspace_access(auth_client):
    response = auth_client.post('/login', data={
        'username': 'tester',
        'password': 'correct-password',
    })
    assert response.status_code == 302
    assert response.headers['Location'] == '/'

    workspace = auth_client.get('/')
    assert workspace.status_code == 200
    assert '课程生产工作台'.encode() in workspace.data


def test_logout_clears_session(auth_client):
    auth_client.post('/login', data={
        'username': 'tester',
        'password': 'correct-password',
    })
    response = auth_client.post('/logout')
    assert response.status_code == 302
    assert response.headers['Location'] == '/login'
    assert auth_client.get('/').status_code == 302


def test_regular_user_only_sees_own_tasks(monkeypatch, temp_dir):
    import web.app as app_module

    monkeypatch.setitem(app_module.app.config, 'LOGIN_DISABLED', False)
    monkeypatch.setattr(app_module, 'AUTH_USERNAME', 'admin')
    monkeypatch.setattr(app_module, 'tasks', {
        'own-task': {
            'status': 'completed',
            'original_name': 'own.pptx',
            'owner_username': 'teacher',
        },
        'other-task': {
            'status': 'completed',
            'original_name': 'other.pptx',
            'owner_username': 'other',
        },
    })
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['username'] = 'teacher'
        sess['role'] = 'user'

    response = client.get('/api/tasks')

    assert response.status_code == 200
    payload = response.get_json()
    assert [task['task_id'] for task in payload['tasks']] == ['own-task']


def test_super_admin_sees_all_tasks(monkeypatch):
    import web.app as app_module

    monkeypatch.setitem(app_module.app.config, 'LOGIN_DISABLED', False)
    monkeypatch.setattr(app_module, 'tasks', {
        'own-task': {
            'status': 'completed',
            'original_name': 'own.pptx',
            'owner_username': 'teacher',
        },
        'other-task': {
            'status': 'completed',
            'original_name': 'other.pptx',
            'owner_username': 'other',
        },
    })
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['username'] = 'admin'
        sess['role'] = 'super_admin'

    response = client.get('/api/tasks')

    assert response.status_code == 200
    assert {task['task_id'] for task in response.get_json()['tasks']} == {
        'own-task',
        'other-task',
    }


def test_tasks_default_order_by_created_at_desc(monkeypatch):
    import web.app as app_module

    monkeypatch.setitem(app_module.app.config, 'LOGIN_DISABLED', False)
    monkeypatch.setattr(app_module, 'tasks', {
        'old-task': {
            'status': 'completed',
            'original_name': 'old.pptx',
            'owner_username': 'teacher',
            'created_at': 1000,
        },
        'new-task': {
            'status': 'completed',
            'original_name': 'new.pptx',
            'owner_username': 'teacher',
            'created_at': 3000,
        },
        'middle-task': {
            'status': 'completed',
            'original_name': 'middle.pptx',
            'owner_username': 'teacher',
            'created_at': 2000,
        },
    })
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['username'] = 'teacher'
        sess['role'] = 'user'

    response = client.get('/api/tasks')

    assert response.status_code == 200
    assert [task['task_id'] for task in response.get_json()['tasks']] == [
        'new-task',
        'middle-task',
        'old-task',
    ]


def test_tasks_uses_fallback_created_time_for_legacy_tasks(monkeypatch):
    import web.app as app_module

    monkeypatch.setitem(app_module.app.config, 'LOGIN_DISABLED', False)
    monkeypatch.setattr(app_module, 'tasks', {
        'legacy-task': {
            'status': 'completed',
            'original_name': 'legacy.pptx',
            'owner_username': 'teacher',
            'updated_at': 2000,
        },
        'new-task': {
            'status': 'completed',
            'original_name': 'new.pptx',
            'owner_username': 'teacher',
            'created_at': 1000,
        },
    })
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['username'] = 'teacher'
        sess['role'] = 'user'

    response = client.get('/api/tasks')

    assert response.status_code == 200
    tasks = response.get_json()['tasks']
    assert [task['task_id'] for task in tasks] == ['legacy-task', 'new-task']
    assert tasks[0]['created_at'] == 2000
    assert tasks[0]['created_at_source'] == 'fallback'


def test_tasks_supports_pagination_and_filters(monkeypatch):
    import web.app as app_module

    monkeypatch.setitem(app_module.app.config, 'LOGIN_DISABLED', False)
    monkeypatch.setattr(app_module, 'tasks', {
        f'task-{index}': {
            'status': 'completed' if index % 2 else 'error',
            'original_name': f'course-{index}.pptx',
            'owner_username': 'teacher',
            'created_at': 1000 + index,
        }
        for index in range(1, 16)
    })
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['username'] = 'teacher'
        sess['role'] = 'user'

    response = client.get('/api/tasks?page=2&page_size=5&status=completed&q=course')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['pagination'] == {
        'page': 2,
        'page_size': 5,
        'total': 8,
        'total_pages': 2,
    }
    assert [task['task_id'] for task in payload['tasks']] == [
        'task-5',
        'task-3',
        'task-1',
    ]


def test_regular_user_cannot_download_other_users_file(monkeypatch, temp_dir):
    import web.app as app_module

    output_dir = temp_dir / 'task'
    output_dir.mkdir()
    video = output_dir / 'video.mp4'
    video.write_bytes(b'video')
    monkeypatch.setitem(app_module.app.config, 'LOGIN_DISABLED', False)
    monkeypatch.setattr(app_module, 'tasks', {
        'task': {
            'status': 'completed',
            'original_name': 'other.pptx',
            'owner_username': 'other',
            'output_dir': str(output_dir),
            'video_path': str(video),
        },
    })
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['username'] = 'teacher'
        sess['role'] = 'user'

    response = client.get(f'/api/download?task_id=task&path={video}')

    assert response.status_code == 403


def test_operation_logs_are_filtered_for_regular_user(monkeypatch, temp_dir):
    import web.app as app_module
    from web.task_store import TaskStore

    store = TaskStore(temp_dir / 'tasks.db')
    store.add_operation_log({'actor': 'teacher', 'role': 'user', 'action': 'upload'})
    store.add_operation_log({'actor': 'other', 'role': 'user', 'action': 'upload'})
    monkeypatch.setitem(app_module.app.config, 'LOGIN_DISABLED', False)
    monkeypatch.setattr(app_module, 'task_store', store)
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['username'] = 'teacher'
        sess['role'] = 'user'

    response = client.get('/api/operation-logs')

    assert response.status_code == 200
    logs = response.get_json()['logs']
    assert len(logs) == 1
    assert logs[0]['actor'] == 'teacher'
