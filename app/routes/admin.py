"""Admin dashboard routes: Private telemetry view, data export, and log maintenance."""
import hmac
from typing import Optional
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import clear_dispatches, get_dispatch_stats, get_dispatches

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="app/templates")


def verify_admin_auth(
    request: Request,
    token: Optional[str] = Query(None),
    admin_session: Optional[str] = Cookie(None),
) -> str:
    """
    Verifies that the request possesses valid admin credentials.
    Checks Authorization header, query parameter ?token=..., or session cookie.
    """
    settings = get_settings()
    expected_token = settings.ADMIN_SECRET_TOKEN

    auth_header = request.headers.get("authorization")
    bearer_token = None
    if auth_header and auth_header.lower().startswith("bearer "):
        bearer_token = auth_header[7:].strip()

    candidate = token or bearer_token or admin_session

    if not candidate or not hmac.compare_digest(candidate, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid ADMIN_SECRET_TOKEN required via Bearer header or ?token= query parameter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return candidate


@router.get("", response_class=HTMLResponse)
def get_admin_dashboard(request: Request, authenticated_token: str = Depends(verify_admin_auth)):
    """Renders the private observatory dashboard."""
    settings = get_settings()
    dispatches = get_dispatches(limit=100)
    stats = get_dispatch_stats()
    webhook_active = bool(settings.DISCORD_WEBHOOK_URL and settings.DISCORD_WEBHOOK_URL.strip())

    response = templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "dispatches": dispatches,
            "stats": stats,
            "admin_token": authenticated_token,
            "webhook_active": webhook_active,
        },
    )
    # Set session cookie so following links in dashboard retains authentication
    response.set_cookie(
        key="admin_session",
        value=authenticated_token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


@router.get("/api/export", response_class=JSONResponse)
def export_dispatches(authenticated_token: str = Depends(verify_admin_auth)):
    """Exports all logged agent dispatches as structured JSON."""
    dispatches = get_dispatches(limit=5000)
    return JSONResponse(content={"count": len(dispatches), "dispatches": dispatches})


@router.post("/api/clear")
def clear_all_dispatches(authenticated_token: str = Depends(verify_admin_auth)):
    """Purges all recorded dispatches from SQLite storage."""
    deleted_count = clear_dispatches()
    return RedirectResponse(url=f"/admin?token={authenticated_token}&purged={deleted_count}", status_code=status.HTTP_303_SEE_OTHER)
