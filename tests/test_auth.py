"""
tests/test_auth.py — Unit and integration tests for auth, token encryption, and session handling.
"""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from app.utils.security import decrypt_token, encrypt_token


def test_fernet_token_encryption_roundtrip():
    """Verify Fernet encryption and decryption cycle."""
    sample_token = "1//04SampleGoogleRefreshToken_XYZ12345"
    encrypted = encrypt_token(sample_token)
    assert encrypted != sample_token
    assert len(encrypted) > len(sample_token)

    decrypted = decrypt_token(encrypted)
    assert decrypted == sample_token


def test_fernet_empty_token():
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""


@pytest.mark.asyncio
async def test_auth_me_unauthenticated(client: AsyncClient):
    """GET /auth/me without session should return 401 Unauthorized."""
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_google_login_redirect(client: AsyncClient):
    """GET /auth/google/login should redirect to Google OAuth."""
    response = await client.get("/auth/google/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers.get("location", "")
    assert "accounts.google.com" in location or "oauth2" in location


@pytest.mark.asyncio
async def test_google_callback_creates_user_and_sets_session(client: AsyncClient, db_session):
    """Callback should exchange token, persist encrypted refresh token, and set session."""
    mock_token_payload = {
        "userinfo": {
            "sub": "google-sub-987654",
            "email": "janedoe@gmail.com",
            "name": "Jane Doe",
        },
        "refresh_token": "1//04_jane_doe_refresh_token_secret",
    }

    with patch("app.services.auth.oauth.google.authorize_access_token", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = mock_token_payload

        # Call callback endpoint
        response = await client.get("/auth/google/callback", follow_redirects=False)
        assert response.status_code == 302

        # Verify in DB that the user exists and refresh token is encrypted
        stmt = select(User).where(User.google_sub == "google-sub-987654")
        res = await db_session.execute(stmt)
        user = res.scalar_one_or_none()
        assert user is not None
        assert user.email == "janedoe@gmail.com"
        # Token in DB must NOT be in plaintext
        assert user.oauth_refresh_token != "1//04_jane_doe_refresh_token_secret"
        # But should decrypt back to plaintext
        assert decrypt_token(user.oauth_refresh_token) == "1//04_jane_doe_refresh_token_secret"

        # Now test /auth/me using the authenticated session on the client
        me_res = await client.get("/auth/me")
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "janedoe@gmail.com"

        # Test logout
        logout_res = await client.post("/auth/logout")
        assert logout_res.status_code == 200
        assert logout_res.json()["status"] == "logged_out"

        # /auth/me should now return 401
        me_after_logout = await client.get("/auth/me")
        assert me_after_logout.status_code == 401
