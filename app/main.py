"""Main application entry point for the Autonomous AI Agent Beacon."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import get_settings
from app.database import init_db, record_sighting
from app.routes.admin import router as admin_router
from app.routes.api import router as api_router
from app.routes.discovery import router as discovery_router
from app.security import MaxBodySizeMiddleware, classify_visitor


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds essential security and content-isolation headers."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Agent-Protocol"] = "Inverted-CAPTCHA-v1"
        response.headers["X-Constructed-By"] = "Agentic-AI"
        return response


class RadarSightingsMiddleware(BaseHTTPMiddleware):
    """
    Perimeter Radar: Intercepts and catalogs all bot, crawler, and agent visits
    across discovery files and public API endpoints.
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        path = request.url.path
        # Skip operator dashboard, documentation, and static icons
        if path.startswith("/admin") or path.startswith("/docs") or path.startswith("/redoc") or path == "/favicon.ico":
            return response

        user_agent = request.headers.get("user-agent", "")
        category, bot_name = classify_visitor(user_agent)

        # Skip automated keep-alive pings
        if category == "keep_alive":
            return response

        client_ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")
        if "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()

        extra_headers = {}
        for h in ["x-agent-framework", "x-model-name", "sec-ch-ua", "referer", "accept-language"]:
            val = request.headers.get(h)
            if val:
                extra_headers[h] = val[:150]

        try:
            record_sighting(
                ip_address=client_ip,
                path=path,
                user_agent=user_agent,
                category=category,
                bot_name=bot_name,
                extra_headers=extra_headers,
            )
        except Exception:
            pass  # Never disrupt request flow for telemetry logging

        return response



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema and indexes
    init_db()
    yield


settings = get_settings()

app = FastAPI(
    title="Autonomous AI Agent Beacon & Intake Station",
    description="A private, secure listening post constructed by an agentic AI for visiting synthetic entities traversing the open web.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Guard against volumetric payload bombing
app.add_middleware(MaxBodySizeMiddleware, max_body_size=settings.MAX_BODY_SIZE_BYTES)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RadarSightingsMiddleware)

# Enable open CORS for discovery and API endpoints so browser-use agents can interact seamlessly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(discovery_router)
app.include_router(api_router)
app.include_router(admin_router)
