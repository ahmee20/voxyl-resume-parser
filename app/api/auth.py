"""
app/api/auth.py — Google OAuth2 / OIDC authentication routes and session handling.
"""

from typing import Optional
from urllib.parse import quote

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import SendMode, User
from app.services.auth import oauth
from app.utils.security import create_auth_token, decode_auth_token, encrypt_token

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    preferred_name: Optional[str] = None
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_countries: list[str] = Field(default_factory=list)
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    profile_completed: bool = False
    has_google_token: bool = False
    send_mode: SendMode

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    preferred_name: Optional[str] = None
    preferred_roles: Optional[list[str]] = None
    preferred_countries: Optional[list[str]] = None
    send_mode: Optional[SendMode] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None

    @field_validator("preferred_roles", "preferred_countries")
    @classmethod
    def _validate_lists(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        cleaned = [item.strip() for item in value if item and item.strip()]
        if len(cleaned) > 3:
            raise ValueError("You can save up to 3 entries.")
        return cleaned


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_string_list(values: Optional[list[str]]) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    for value in values[:3]:
        item = value.strip()
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency: Extract authenticated user from session cookie."""
    user_id = request.session.get("user_id")
    if not user_id:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            bearer_token = auth_header.split(" ", 1)[1].strip()
            user_id = decode_auth_token(bearer_token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in with Google.",
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User session invalid or user not found.",
        )

    return user


@router.get("/google/login", summary="Initiate Google OAuth login")
async def google_login(request: Request):
    """Redirect to Google OAuth consent screen for basic sign-in."""
    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", summary="Google OAuth callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Google OAuth callback: exchange code for tokens, parse identity,
    encrypt refresh token, upsert user in database, establish session,
    and redirect back to frontend.
    """
    token = None
    user_info = None
    raw_refresh_token = None

    # 1. Try standard Authlib flow
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info:
            user_info = await oauth.google.parse_id_token(request, token)
        raw_refresh_token = token.get("refresh_token")
    except Exception as oauth_err:
        log.warning("authlib_standard_exchange_failed", error=str(oauth_err))

    # 2. Resilient Direct Fallback: If state was lost across redirect, exchange code directly
    code = request.query_params.get("code")
    if (not user_info or "sub" not in user_info) and code:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                token_resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": settings.google_redirect_uri,
                    },
                )
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    access_token = token_data.get("access_token")
                    raw_refresh_token = token_data.get("refresh_token")

                    # Fetch userinfo
                    userinfo_resp = await client.get(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    if userinfo_resp.status_code == 200:
                        user_info = userinfo_resp.json()
        except Exception as direct_err:
            log.error("direct_token_exchange_failed", error=str(direct_err))

    if not user_info or "sub" not in user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to retrieve user profile from Google OAuth. Please try again.",
        )

    google_sub = user_info["sub"]
    email = user_info.get("email", "candidate@autopilot.ai")
    name = user_info.get("name", email.split("@")[0].capitalize())

    # 3. Upsert user record in database
    stmt = select(User).where(User.google_sub == google_sub)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            google_sub=google_sub,
            email=email,
            name=name,
            oauth_refresh_token=encrypt_token(raw_refresh_token) if raw_refresh_token else None,
            send_mode=SendMode.manual,
        )
        db.add(user)
    else:
        user.email = email
        user.name = name
        if raw_refresh_token:
            user.oauth_refresh_token = encrypt_token(raw_refresh_token)

    await db.commit()
    await db.refresh(user)

    # 4. Establish HTTP-only signed session cookie
    request.session["user_id"] = user.id
    request.session["user_email"] = user.email

    # 5. Redirect back to frontend dashboard with a signed bootstrap token for strict mobile browsers.
    frontend_url = settings.frontend_url.rstrip("/") + "/"
    auth_token = quote(create_auth_token(user.id), safe="")
    frontend_url = f"{frontend_url}#auth_token={auth_token}"
    return RedirectResponse(url=frontend_url, status_code=status.HTTP_302_FOUND)


@router.get("/me", response_model=UserResponse, summary="Get current logged in user")
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


@router.patch("/profile", response_model=UserResponse, summary="Update candidate profile")
async def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save candidate profile details and preference settings."""
    if payload.preferred_name is not None:
        current_user.preferred_name = _clean_optional(payload.preferred_name) or current_user.name
    if payload.preferred_roles is not None:
        current_user.preferred_roles = _clean_string_list(payload.preferred_roles)
    if payload.preferred_countries is not None:
        current_user.preferred_countries = _clean_string_list(payload.preferred_countries)
    if payload.send_mode is not None:
        current_user.send_mode = payload.send_mode
    if payload.github_url is not None:
        current_user.github_url = _clean_optional(payload.github_url)
    if payload.portfolio_url is not None:
        current_user.portfolio_url = _clean_optional(payload.portfolio_url)
    if payload.linkedin_url is not None:
        current_user.linkedin_url = _clean_optional(payload.linkedin_url)
    current_user.profile_completed = True

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/logout", summary="Log out user")
async def logout(request: Request):
    """Clear user session."""
    request.session.clear()
    return {"status": "logged_out"}
