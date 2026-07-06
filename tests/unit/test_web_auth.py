"""Web 登录与访问保护测试。"""

import pytest


@pytest.fixture
def auth_client(monkeypatch):
    import web.app as app_module

    monkeypatch.setattr(app_module, 'AUTH_USERNAME', 'tester')
    monkeypatch.setattr(app_module, 'AUTH_PASSWORD', 'correct-password')
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
