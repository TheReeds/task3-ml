"""Límite de peticiones por cliente, en memoria del proceso.

Cubetas de tokens por (regla, cliente). El cliente se identifica por la IP que informa el proxy
(`CF-Connecting-IP` de Cloudflare, luego `X-Forwarded-For`, luego la conexión). La IP solo se usa
en memoria para contar; no se guarda. Con varios procesos cada uno cuenta por separado: para
producción habría que moverlo a un almacén compartido (Redis).
"""

import re
import time
from dataclasses import dataclass

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class Rule:
    name: str
    method: str
    pattern: re.Pattern
    per_minute: int
    burst: int


def rule(name: str, method: str, path: str, per_minute: int, burst: int | None = None) -> Rule:
    return Rule(name, method, re.compile(path), per_minute, burst or per_minute)


DEFAULT_RULES = (
    rule("sesiones", "POST", r"^/auth/anonymous$", 10, 5),
    rule("vinculacion", "POST", r"^/auth/link(-code)?$", 10, 5),
    rule("aportes", "POST", r"^/contributions(/audio)?$", 30, 10),
    rule("revisiones", "POST", r"^/taller/reviews$", 60, 20),
    rule("radar", "POST", r"^/radar/guess$", 60, 20),
    rule("eventos", "POST", r"^/events$", 60, 20),
    rule("salas", "POST", r"^/duo/rooms(/[^/]+/(join|leave))?$", 20, 10),
    rule("general", "*", r"^/", 600, 120),
)


class RateLimiter:
    def __init__(self, app: ASGIApp, rules=DEFAULT_RULES, enabled: bool = True) -> None:
        self.app, self.rules, self.enabled = app, rules, enabled
        self.buckets: dict[tuple[str, str], tuple[float, float]] = {}
        self.last_sweep = time.monotonic()

    @staticmethod
    def client_key(scope: Scope) -> str:
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        if ip := headers.get("cf-connecting-ip"):
            return ip.strip()
        if fwd := headers.get("x-forwarded-for"):
            return fwd.split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else "desconocido"

    def _take(self, r: Rule, key: str, now: float) -> float | None:
        """Consume un token; devuelve None si se permite o los segundos a esperar."""
        rate = r.per_minute / 60
        tokens, last = self.buckets.get((r.name, key), (float(r.burst), now))
        tokens = min(r.burst, tokens + (now - last) * rate)
        if tokens < 1:
            self.buckets[(r.name, key)] = (tokens, now)
            return (1 - tokens) / rate
        self.buckets[(r.name, key)] = (tokens - 1, now)
        return None

    def _sweep(self, now: float) -> None:
        if now - self.last_sweep > 300:  # cubetas llenas de nuevo: se olvidan
            self.buckets = {k: v for k, v in self.buckets.items() if now - v[1] < 600}
            self.last_sweep = now

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.enabled or scope["type"] != "http":
            return await self.app(scope, receive, send)
        now = time.monotonic()
        self._sweep(now)
        key, method, path = self.client_key(scope), scope["method"], scope["path"]
        for r in self.rules:
            if r.method in ("*", method) and r.pattern.match(path):
                wait = self._take(r, key, now)
                if wait is not None:
                    retry = max(1, int(wait + 0.999))
                    response = JSONResponse(
                        {"detail": "Demasiadas solicitudes; intenta de nuevo en unos segundos"},
                        status_code=429, headers={"Retry-After": str(retry)})
                    return await response(scope, receive, send)
        await self.app(scope, receive, send)
