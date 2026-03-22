from app.core.settings import get_settings


def test_bot_api_token_auth_works_for_protected_route(client):
    c, _ = client
    settings = get_settings()
    settings.bot_api_token = "bot-fixed-token"

    c.headers.clear()
    c.headers.update({"Authorization": "Bearer bot-fixed-token"})
    resp = c.get("/api/v1/users/me")

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == settings.bot_service_email


def test_bot_api_token_can_impersonate_telegram_user(client):
    c, _ = client
    settings = get_settings()
    settings.bot_api_token = "bot-fixed-token"

    c.headers.clear()
    c.headers.update(
        {
            "Authorization": "Bearer bot-fixed-token",
            "X-Telegram-User-Id": "999001",
        }
    )
    resp = c.get("/api/v1/users/me")

    assert resp.status_code == 200
    body = resp.json()
    assert body["telegram_id"] == "999001"
