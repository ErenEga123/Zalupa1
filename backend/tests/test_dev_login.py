from app.core.settings import get_settings


def test_dev_login_returns_tokens_when_not_prod(client):
    c, _ = client
    settings = get_settings()
    settings.app_env = "dev"

    resp = c.post('/api/v1/auth/dev/login', json={'email': 'dev@example.com'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['access_token']
    assert data['refresh_token']


def test_dev_login_blocked_in_prod(client):
    c, _ = client
    settings = get_settings()
    settings.app_env = "prod"

    resp = c.post('/api/v1/auth/dev/login', json={'email': 'dev@example.com'})
    assert resp.status_code == 404

    settings.app_env = "dev"
