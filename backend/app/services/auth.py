"""Identidad anónima con vinculación posterior (§9.2).

Cada dispositivo tiene su propio token opaco (solo se guarda su hash). Para usar la misma
identidad —confiabilidad y aportes— en otro dispositivo, el primero genera un código de un solo
uso y corta vida que el segundo canjea por un token nuevo. No hay correo ni datos personales.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Contributor, ContributorToken, LinkCode

LINK_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I: se dicta o se copia
LINK_CODE_LENGTH = 8
LINK_CODE_TTL = timedelta(minutes=10)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue_token(db: Session, contributor: Contributor) -> str:
    token = secrets.token_urlsafe(32)
    db.add(ContributorToken(token_hash=hash_secret(token), contributor_id=contributor.id))
    return token


def create_contributor(db: Session) -> tuple[Contributor, str]:
    contributor = Contributor(reliability=0.5)
    db.add(contributor)
    db.flush()
    token = issue_token(db, contributor)
    db.commit()
    return contributor, token


def contributor_by_token(db: Session, token: str | None) -> Contributor | None:
    if not token:
        return None
    return db.scalars(
        select(Contributor).join(ContributorToken, ContributorToken.contributor_id == Contributor.id)
        .where(ContributorToken.token_hash == hash_secret(token))
    ).first()


def create_link_code(db: Session, contributor: Contributor) -> tuple[str, datetime]:
    code = "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(LINK_CODE_LENGTH))
    expires = datetime.now(UTC) + LINK_CODE_TTL
    db.add(LinkCode(code_hash=hash_secret(code), contributor_id=contributor.id, expires_at=expires))
    db.commit()
    return code, expires


def redeem_link_code(db: Session, code: str) -> tuple[Contributor, str] | None:
    """Canjea el código por un token nuevo de la misma identidad. None si no es válido."""
    normalized = "".join(code.split()).upper().replace("-", "")
    link = db.scalars(
        select(LinkCode).where(LinkCode.code_hash == hash_secret(normalized)).with_for_update()
    ).first()
    now = datetime.now(UTC)
    if link is None or link.used_at is not None or link.expires_at < now:
        return None
    link.used_at = now
    contributor = db.get(Contributor, link.contributor_id)
    token = issue_token(db, contributor)
    db.commit()
    return contributor, token
