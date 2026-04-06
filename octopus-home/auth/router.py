"""OAuth2 authorization code flow for Alexa and Google Home account linking."""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import delete, select

from auth.models import OAuthCode, OAuthToken
from auth.service import (
    create_access_token,
    create_authorization_code,
    create_refresh_token,
    decode_token,
)
from core.database import async_session_factory

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Allowed OAuth2 clients (Alexa + Google). In production, store in DB or config.
ALLOWED_CLIENTS = {
    "alexa": True,
    "google": True,
}

# Demo user — in production replace with real user authentication
DEMO_USER_ID = "homeuser1"


@router.get("/authorize")
async def authorize(
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    state: str = Query(...),
    response_type: str = Query("code"),
):
    """Issue an authorization code and redirect back to the client.

    In production this endpoint would show a login page. For this demo
    it auto-approves the DEMO_USER_ID.
    """
    if response_type != "code":
        raise HTTPException(status_code=400, detail="Only response_type=code is supported")
    if client_id not in ALLOWED_CLIENTS:
        raise HTTPException(status_code=400, detail="Unknown client_id")

    code = create_authorization_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    async with async_session_factory() as session:
        session.add(
            OAuthCode(
                code=code,
                client_id=client_id,
                redirect_uri=redirect_uri,
                user_id=DEMO_USER_ID,
                expires_at=expires_at,
            )
        )
        await session.commit()

    params = urlencode({"code": code, "state": state})
    return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=302)


@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str = Form(None),
    refresh_token: str = Form(None),
    client_id: str = Form(...),
    client_secret: str = Form(None),
    redirect_uri: str = Form(None),
):
    """Exchange authorization code or refresh token for access + refresh tokens."""
    if grant_type == "authorization_code":
        if not code:
            raise HTTPException(status_code=400, detail="code is required")

        async with async_session_factory() as session:
            result = await session.execute(select(OAuthCode).where(OAuthCode.code == code))
            auth_code = result.scalar_one_or_none()

        if auth_code is None:
            raise HTTPException(status_code=400, detail="Invalid authorization code")
        if auth_code.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Authorization code expired")
        if auth_code.client_id != client_id:
            raise HTTPException(status_code=400, detail="client_id mismatch")

        user_id = auth_code.user_id

        # Consume the code
        async with async_session_factory() as session:
            await session.execute(delete(OAuthCode).where(OAuthCode.code == code))
            await session.commit()

    elif grant_type == "refresh_token":
        if not refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token is required")

        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid refresh token")
        user_id = payload["sub"]

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")

    access_token, access_expires_at = create_access_token(user_id, client_id)
    new_refresh_token, refresh_expires_at = create_refresh_token(user_id, client_id)

    async with async_session_factory() as session:
        session.add(
            OAuthToken(
                access_token=access_token,
                refresh_token=new_refresh_token,
                client_id=client_id,
                user_id=user_id,
                expires_at=access_expires_at,
            )
        )
        await session.commit()

    return JSONResponse({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": new_refresh_token,
    })
