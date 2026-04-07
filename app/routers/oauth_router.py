"""OAuth endpoints for channel installations (Slack, etc.)."""

from __future__ import annotations

import base64
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy.orm import Session

from app.commands.install_channel_command import InstallChannelCommand
from app.config import get_settings
from app.db import get_db
from tessera_sdk.server.dependencies.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])

# Bot token scopes required for Slack DM integration
_SLACK_BOT_SCOPES = "chat:write,im:history,im:read"


def _encode_state(tessera_user_id: str) -> str:
    return base64.urlsafe_b64encode(tessera_user_id.encode()).decode()


def _decode_state(state: str) -> Optional[str]:
    try:
        return base64.urlsafe_b64decode(state.encode()).decode()
    except Exception:
        return None


@router.post("/slack/install")
async def slack_install(
    current_user=Depends(get_current_user),
) -> dict[str, str]:
    """Build Slack OAuth consent URL for authenticated Tessera user."""
    settings = get_settings()
    if not settings.slack_client_id:
        raise HTTPException(status_code=503, detail="Slack integration not configured")

    state = _encode_state(str(current_user.id))
    url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={settings.slack_client_id}"
        f"&scope={_SLACK_BOT_SCOPES}"
        f"&state={state}"
    )
    return {"authorize_url": url}


@router.get("/slack/callback")
async def slack_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Handle Slack OAuth callback: exchange code, store installation, fire event."""
    settings = get_settings()
    if not settings.slack_client_id or not settings.slack_client_secret:
        raise HTTPException(status_code=503, detail="Slack integration not configured")

    tessera_user_id = _decode_state(state)
    if not tessera_user_id:
        raise HTTPException(status_code=400, detail="Invalid OAuth state parameter")

    client = AsyncWebClient()
    try:
        response = await client.oauth_v2_access(
            client_id=settings.slack_client_id,
            client_secret=settings.slack_client_secret,
            code=code,
        )
    except Exception as exc:
        logger.exception("Slack OAuth token exchange failed")
        raise HTTPException(
            status_code=502, detail="Slack token exchange failed"
        ) from exc

    if not response.get("ok"):
        logger.error("Slack OAuth error: %s", response.get("error"))
        raise HTTPException(status_code=502, detail="Slack OAuth error")

    team = response.get("team") or {}
    bot = response.get("bot_user_id") or (response.get("authed_user") or {}).get("id")
    access_token = response.get("access_token")
    scopes = response.get("scope") or _SLACK_BOT_SCOPES
    installer_user_id = (response.get("authed_user") or {}).get("id")

    command = InstallChannelCommand(db)
    command.execute(
        channel="slack",
        account_id=team.get("id") or "",
        account_name=team.get("name"),
        bot_user_id=bot,
        installer_user_id=installer_user_id,
        scopes=scopes,
        sensitive_data={"bot_token": access_token},
        tessera_user_id=tessera_user_id,
    )

    success_url = settings.slack_oauth_success_url or "/"
    return RedirectResponse(url=success_url)
