from sqlalchemy import select

from app.models.user import EmailMagicLinkToken


def test_basic_auth_magic_link_flow(client):
    c, Session = client
    req = c.post("/api/v1/auth/magic/request", json={"email": "reader@example.com"})
    assert req.status_code == 200

    with Session() as db:
        token = db.scalar(select(EmailMagicLinkToken.token))

    consume = c.post("/api/v1/auth/magic/consume", json={"token": token})
    assert consume.status_code == 200
    data = consume.json()
    assert data["access_token"]
    assert data["refresh_token"]

    reuse = c.post("/api/v1/auth/magic/consume", json={"token": token})
    assert reuse.status_code == 401
