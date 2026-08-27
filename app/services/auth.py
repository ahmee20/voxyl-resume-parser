"""
app/services/auth.py — Google OAuth2 / OpenID Connect client via Authlib.
"""

from authlib.integrations.starlette_client import OAuth
from app.config import settings

oauth = OAuth()

GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
]

oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": " ".join(GOOGLE_SCOPES),
    },
)
