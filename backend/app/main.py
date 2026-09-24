import mimetypes

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import contributions, corpus, duo, lente, meta, metrics, radar, taller
from app.api.deps import DB
from app.config import get_settings
from app.ratelimit import RateLimiter

settings = get_settings()

# Las imágenes Docker mínimas no traen /etc/mime.types: sin esto el audio sale como
# application/octet-stream y algunos navegadores no lo reproducen
mimetypes.add_type("audio/ogg", ".ogg")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("image/jpeg", ".jpg")

app = FastAPI(
    title="Corpus Vivo API",
    description="Servicio de aplicación de Corpus Vivo: Radio, Radar, Lente, Dúo y Taller.",
    version="0.1.0",
)
app.add_middleware(RateLimiter, enabled=settings.rate_limit_enabled)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(corpus.router)
app.include_router(contributions.router)
app.include_router(taller.router)
app.include_router(radar.router)
app.include_router(lente.router)
app.include_router(duo.router)
app.include_router(metrics.router)
app.include_router(meta.router)

settings.media_dir.mkdir(parents=True, exist_ok=True)
app.mount(settings.media_url, StaticFiles(directory=settings.media_dir), name="media")


@app.get("/health", tags=["meta"])
def health(db: DB):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "adapter": settings.model_adapter, "default_lang": settings.default_lang}
