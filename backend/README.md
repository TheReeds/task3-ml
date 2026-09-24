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
uv run python -m pipeline.seed_gold      # elementos de control para el Taller
uv run python -m pipeline.build_lente    # etiquetas de visión (COCO-SSD) → lemas
uv run python -m pipeline.build_lexeme_audio  # pronunciación TTS de cada lema
uv run python -m pipeline.build_duo_images    # catálogo Dúo: Wikimedia Commons + filtro CLIP
uv run python -m pipeline.build_audio_fallback  # copias AAC (.m4a) para iOS
uv run python -m pipeline.build_topics   # temas de Radio (agrupamiento; --apply-only para otra base)

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

## Endpoints

| Método | Ruta | Uso |
|---|---|---|
| GET | `/languages` | Lenguas con datos y módulos disponibles |
| GET | `/radio/stations` | Emisoras (aleatoria, dificultad, temas `dominio:<slug>`) |
| GET | `/radio/stations/{id}/next?after=` | Siguiente entrada: texto, audio, tokens con tiempos, traducción |
| GET | `/entries/{id}` · `/entries/{id}/history` | Entrada y su cadena de versiones |
| GET | `/lexemes?q=` | Búsqueda por lema, forma flexionada o glosa |
| GET | `/lexemes/{id}` | Panel de palabra: lema, glosa, frecuencia, ejemplos |
| POST | `/auth/anonymous` | Token anónimo para contribuir |
| POST | `/auth/link-code` · `/auth/link` | Vincular otro dispositivo a la misma identidad |
| POST | `/contributions` | `transcription_fix` · `translation_fix` · `gloss_fix` · `new_lemma` |
| GET | `/contributions/mine` | Contribuciones propias y su estado |
| PATCH | `/auth/me` | Declararse hablante nativo |
| GET | `/media/...` | Audio Ogg/Opus (soporta Range) |
| GET | `/taller/next?type=` | Siguiente contribución a revisar, filtrable por tipo (204 si no hay) |
| POST | `/taller/reviews` | Juicio `accept` · `reject` · `unsure` |
| GET | `/taller/impact?days=` | Panel de impacto (kappa de Fleiss y serie diaria) |
| GET | `/taller/export?format=jsonl\|csv` | Contribuciones aprobadas con atribución anónima |
| GET | `/radar/today` | Puzzle del día: letras, tamaño del vocabulario, pistas |
| POST | `/radar/guess` | Intento → lema, glosa, percentil, rango; si no existe, sugerencia de aporte |
| GET | `/radar/puzzles?days=` | Archivo de días anteriores |
| GET | `/radar/puzzles/{id}/answer?give_up=true` | Respuesta y vecinos más cercanos |
| GET | `/lente/labels?gaps_only=` | Tabla etiqueta de visión → lema + audio (el cliente la cachea) |
| POST | `/contributions/audio` | Grabación de pronunciación (multipart, `consent=true`, 0,3–6 s) |
| POST | `/duo/rooms` | Crear sala; devuelve el código de 6 caracteres |
| POST | `/duo/rooms/{code}/join` | Unirse (o reconectarse) |
| GET | `/duo/rooms/{code}` | Vista de la sala para quien consulta |
| PUT | `/duo/rooms/{code}/consent` | Dar o revocar consentimiento de captura de texto |
| POST | `/duo/rooms/{code}/leave` | Salir (cierra la sala para ambos) |
| WS | `/duo/ws/{code}?token=&device_id=` | Partida en tiempo real (ver protocolo abajo) |
| POST | `/events` | Eventos de uso del cliente (cabecera `X-Device-Id`) |
| GET | `/metrics?days=` | Métricas de evaluación (§12) |

Todas las rutas tienen límite de peticiones por cliente (429 + `Retry-After`); se desactiva con
`RATE_LIMIT_ENABLED=false`.

## Taller: reglas de consenso

- Puntaje = Σ(peso·veredicto) / Σpeso, sin contar `unsure` (§7.3).
- Se resuelve con ≥ 2 juicios firmes y peso acumulado ≥ 1,5 (3 revisores nuevos o 2 expertos),
  aceptando con puntaje ≥ 0,7 y rechazando con ≤ 0,3. Tras 7 juicios sin consenso se rechaza.
- Confiabilidad = acierto Beta(1,1) sobre controles, en [0,1; 0,8]; solo hablantes nativos con
  ≥ 5 controles y ≥ 80 % de acierto pueden llegar a 1. La primera revisión y luego una de cada 5
  es un control, indistinguible de una contribución real.
- Una contribución aceptada crea una versión nueva; si el destino cambió entretanto queda `stale`.

Todos los umbrales se configuran en `app/config.py` (variables de entorno).

## Radar

- Vocabulario del juego: raíces vigentes con vector (se excluyen formas flexionadas del
  diccionario). Palabra del día: raíz de contenido con frecuencia ≥ 50, no préstamo.
- El intento se normaliza y reduce a raíz ("wasikunapi" → wasi, "maskaspa" → maskay).
- El ranking completo se calcula una vez al día (zona America/Lima) y se guarda con el puzzle.

## Lente

- La cámara y la clasificación viven en el navegador (TensorFlow.js, COCO-SSD); el servidor
  nunca recibe imágenes. Solo publica la tabla etiqueta → lema con su audio.
- La tabla se construye por diccionario (glosa inversa) y, como respaldo, por el modelo con
  validación ida y vuelta; siempre exige lema atestiguado en el corpus. 17/80 etiquetas cubiertas.
- Las etiquetas sin lema son vacíos: `new_lemma` con `vision_label` propone la palabra (nueva o ya
  existente en el corpus) y, al aprobarse en el Taller, queda enlazada con método `community`.

## Dúo

- Protocolo WebSocket — cliente envía `{"action": "start_round" | "describe" | "guess" | "consent", ...}`;
  el servidor responde a cada participante con su vista `{"type": "state", ...}` tras cada cambio,
  o `{"type": "error", "status", "detail"}`. Cada rol solo recibe lo que le corresponde ver: el
  adivinador nunca recibe el concepto de las opciones hasta el resultado.
- Distractores: 3 conceptos distintos con similitud CLIP en una ventana centrada en la
  dificultad de la sala. Escalera ponderada (+0,07 al acertar, −0,13 al fallar) → acierto ≈ 65 %.
- Panel auxiliar del descriptor: lema del concepto y 5 lemas relacionados del corpus.
- La descripción se rechaza si nombra el concepto en español.
- Captura: solo con consentimiento del descriptor, como `new_sentence` pendiente de Taller.
  Revocarlo marca lo capturado como `withdrawn`, borra el texto y lo excluye de la exportación.
- Las conexiones viven en memoria del proceso: con varios workers se necesitaría Redis pub/sub.
- Catálogo: imágenes con licencia libre de Wikimedia Commons (autor y licencia guardados para la
  atribución), filtradas con clasificación zero-shot de CLIP contra todos los conceptos.

## Corpus provisional

Hasta recibir el corpus y el modelo del curso se usan recursos públicos (quechua `quy`):
AmericasNLP 2021 (texto paralelo y diccionario), NLLB-200 (traducción), MMS-TTS (audio
**sintético**, marcado `audio_origin = synthetic`) y MMS_FA (alineación forzada).

Para integrar los entregables reales: implementar `app/adapters/remote.py` con el contrato de
`base.py`, adaptar `pipeline/build_corpus.py` al formato del corpus recibido y re-ejecutar la
ingesta. Para aimara: añadir `ayr` al pipeline (NLLB ya soporta `ayr_Latn`).

> La ingesta regenera ids y se niega a correr si hay contribuciones sobre la lengua (`--force`
> solo en desarrollo).
