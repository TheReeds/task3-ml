# Imagen de la API de Corpus Vivo para Hugging Face Spaces (SDK docker)
FROM python:3.12-slim

# ffmpeg: normalización de grabaciones aportadas (Lente)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Spaces ejecuta el contenedor con el usuario 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user . .

ENV MODEL_ADAPTER=hf
EXPOSE 7860
# Las migraciones son idempotentes: dejan el esquema al día en cada arranque
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port 7860 --proxy-headers --forwarded-allow-ips="*"
