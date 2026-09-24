"""Despliegue de la API en un Space de Hugging Face (SDK docker) con base de datos en Neon.

Arma un directorio con el código de la API, las migraciones, el audio/imágenes y los vectores,
lo sube al Space y configura los secretos. No sube credenciales ni el pipeline de ML.

Requiere en backend/.env.deploy (ignorado por git):
    HF_TOKEN='hf_…'            token con permiso de escritura en Spaces
    NEON_URL='postgresql://…'  cadena de conexión de Neon (endpoint con pooler)

Uso: uv run --with huggingface_hub python deploy/deploy_hf.py [--space corpus-vivo-api] [--private]
"""

import argparse
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

BACKEND = Path(__file__).resolve().parent.parent
SPACE_FILES = BACKEND / "deploy" / "hf-space"


def read_env(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip("'\"")
    return env


def stage(dest: Path) -> None:
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(BACKEND / "app", dest / "app", ignore=ignore)
    shutil.copytree(BACKEND / "alembic", dest / "alembic", ignore=ignore)
    shutil.copy(BACKEND / "alembic.ini", dest)
    # aportes de usuarios (contrib/) y manifiestos de búsqueda no se publican
    shutil.copytree(BACKEND / "data" / "media", dest / "data" / "media",
                    ignore=shutil.ignore_patterns("contrib", "manifest*.json"))
    shutil.copytree(BACKEND / "data" / "models", dest / "data" / "models")
    for f in SPACE_FILES.iterdir():
        shutil.copy(f, dest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--space", default="corpus-vivo-api")
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()

    env = read_env(BACKEND / ".env.deploy")
    api = HfApi(token=env["HF_TOKEN"])
    repo_id = f"{api.whoami()['name']}/{args.space}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", private=args.private, exist_ok=True)

    database_url = env["NEON_URL"].replace("postgresql://", "postgresql+psycopg://", 1)
    api.add_space_secret(repo_id, "DATABASE_URL", database_url)
    api.add_space_variable(repo_id, "CORS_ORIGINS", '["*"]')
    api.add_space_variable(repo_id, "DEFAULT_LANG", "quy")

    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp))
        api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=tmp,
                          commit_message="Despliegue de la API", delete_patterns=["app/**", "alembic/**"])
    host = repo_id.replace("/", "-").lower().replace("_", "-")
    print(f"Space: https://huggingface.co/spaces/{repo_id}")
    print(f"API:   https://{host}.hf.space  (docs en /docs)")


if __name__ == "__main__":
    main()
