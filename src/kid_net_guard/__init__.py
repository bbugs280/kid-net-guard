"""kid-net-guard — Open source parental internet toggle console."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from kid_net_guard.api import router as api_router
from kid_net_guard.config import settings

app = FastAPI(title="Kid Net Guard", version=settings.VERSION)

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
