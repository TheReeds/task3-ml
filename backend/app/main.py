from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import contributions, corpus, radar, taller
from app.api.deps import DB
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Corpus Vivo API",
    description="Servicio de aplicación de Corpus Vivo: Radio, Radar, Lente, Dúo y Taller.",
    version="0.1.0",
)
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

settings.media_dir.mkdir(parents=True, exist_ok=True)
app.mount(settings.media_url, StaticFiles(directory=settings.media_dir), name="media")


@app.get("/health", tags=["meta"])
def health(db: DB):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "adapter": settings.model_adapter, "default_lang": settings.default_lang}
