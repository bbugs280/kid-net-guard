"""kid-net-guard — Open source parental internet toggle console."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from kid_net_guard.api import router as api_router
from kid_net_guard.adguard import AdGuardClient
from kid_net_guard.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: ensure AdGuard protection is on and client exists."""
    client = AdGuardClient()
    try:
        await client.ensure_protection_enabled()
    except Exception:
        pass  # AdGuard might not be ready yet — API startup handler will retry
    yield  # Shutdown: nothing to clean up


app = FastAPI(title="Kid Net Guard", version=settings.VERSION, lifespan=lifespan)

# API routes
app.include_router(api_router, prefix="/api")

# Static PWA files
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(settings.STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.VERSION}
