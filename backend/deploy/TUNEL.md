# API de desarrollo por túnel (temporal)

Mientras no haya hosting, la API corre en la PC de desarrollo contra la base de Neon y se publica
con un Cloudflare Quick Tunnel (sin cuenta). Ambos contenedores se reinician solos.

```bash
docker ps --filter name=corpus-vivo-              # corpus-vivo-api y corpus-vivo-tunnel
docker logs corpus-vivo-tunnel 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | head -1   # URL actual
docker logs -f corpus-vivo-api                    # peticiones en vivo
```

Actualizar el código de la API (la URL del túnel no cambia):

```bash
cd backend && . ./.env.deploy
uv run --with huggingface_hub python -c "import sys; sys.path.insert(0,'deploy'); from pathlib import Path; import deploy_hf; deploy_hf.stage(Path('/tmp/cv-stage'))"
docker build -t corpus-vivo-api /tmp/cv-stage && rm -rf /tmp/cv-stage
docker rm -f corpus-vivo-api && docker run -d --name corpus-vivo-api --restart unless-stopped \
  -p 127.0.0.1:7860:7860 -e CORS_ORIGINS='["*"]' \
  -e DATABASE_URL="$(echo $NEON_URL | sed 's#^postgresql://#postgresql+psycopg://#')" corpus-vivo-api
```

Si se reinicia `corpus-vivo-tunnel` (o la PC), **la URL cambia**: actualízala en
`docs/frontend/README.md` §4 y avisa a los agentes. Detener todo:
`docker rm -f corpus-vivo-tunnel corpus-vivo-api`.

Límites: responde solo con la PC encendida; latencia ~1 s (PC en Perú, Neon en Ohio); las
grabaciones subidas viven dentro del contenedor y se pierden al recrearlo.
