"""Main application entry point for the Autonomous AI Agent Beacon."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import get_settings
from app.database import init_db
from app.routes.admin import router as admin_router
from app.routes.api import router as api_router
from app.routes.discovery import router as discovery_router
from app.security import MaxBodySizeMiddleware


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
