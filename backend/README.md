# Corpus Vivo — backend

Servicio de aplicación (FastAPI + PostgreSQL/pgvector) y pipeline de preprocesamiento.
Especificación: `../corpus-vivo-documento-tecnico_*.docx`. Viabilidad: `docs/fase0-viabilidad.md`.

## Puesta en marcha

Requisitos: Docker, ffmpeg, [uv](https://docs.astral.sh/uv/). GPU NVIDIA opcional (acelera el pipeline).

```bash
cd backend
cp .env.example .env
docker compose up -d                     # Postgres + pgvector en el puerto 5433
uv sync --extra ml                       # sin --extra ml si solo se usa MODEL_ADAPTER=mock
uv run alembic upgrade head

# Pipeline (una sola vez; ~5 min con GPU)
uv run python -m pipeline.fetch_sources  # AmericasNLP + fastText → data/raw
uv run python -m pipeline.build_lexicon  # lemas, glosas y vectores → data/models
uv run python -m pipeline.build_corpus   # audio TTS + alineación → data/media
uv run python -m pipeline.ingest         # carga en la base

uv run uvicorn app.main:app --reload     # http://localhost:8000/docs
```

Pruebas: `uv run pytest` (usan la base `corpus_vivo_test` y el adaptador mock).

## Estructura

```
app/
  adapters/      contrato con el modelo (§10.2): base, mock, hf  ← MODEL_ADAPTER
  api/           routers HTTP
  nlp/quechua.py normalización ortográfica y lematizador por sufijos
  services/      lógica de dominio (versión vigente, emisoras de Radio)
  models.py      esquema (§8), inmutable con supersedes_id + vistas current_*
pipeline/        preprocesamiento offline (§9.3)
alembic/         migraciones
tests/
```

## Endpoints (fase 1)

| Método | Ruta | Uso |
|---|---|---|
| GET | `/radio/stations` | Emisoras disponibles con su número de entradas |
| GET | `/radio/stations/{id}/next?after=` | Siguiente entrada: texto, audio, tokens con tiempos, traducción |
| GET | `/entries/{id}` · `/entries/{id}/history` | Entrada y su cadena de versiones |
| GET | `/lexemes/{id}` | Panel de palabra: lema, glosa, frecuencia, ejemplos |
| POST | `/auth/anonymous` | Token anónimo para contribuir |
| POST | `/contributions` | `transcription_fix` · `translation_fix` · `gloss_fix` · `new_lemma` |
| GET | `/contributions/mine` | Contribuciones propias y su estado |
| GET | `/media/...` | Audio Ogg/Opus (soporta Range) |

## Corpus provisional

Hasta recibir el corpus y el modelo del curso se usan recursos públicos (quechua `quy`):
AmericasNLP 2021 (texto paralelo y diccionario), NLLB-200 (traducción), MMS-TTS (audio
**sintético**, marcado `audio_origin = synthetic`) y MMS_FA (alineación forzada).

Para integrar los entregables reales: implementar `app/adapters/remote.py` con el contrato de
`base.py`, adaptar `pipeline/build_corpus.py` al formato del corpus recibido y re-ejecutar la
ingesta. Para aimara: añadir `ayr` al pipeline (NLLB ya soporta `ayr_Latn`).

> La ingesta regenera ids y se niega a correr si hay contribuciones sobre la lengua (`--force`
> solo en desarrollo).
