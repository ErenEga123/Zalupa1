import httpx

from app.core.settings import get_settings


settings = get_settings()


async def exchange_google_code(code: str) -> dict | None:
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code >= 400:
            return None
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return None

        profile_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code >= 400:
            return None
        return profile_resp.json()
