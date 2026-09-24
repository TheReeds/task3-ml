from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ratelimit import RateLimiter, rule


def make_client(**kw):
    app = FastAPI()

    @app.post("/auth/anonymous")
    def anon():
        return {"ok": True}

    @app.get("/libre")
    def libre():
        return {"ok": True}

    app.add_middleware(RateLimiter, rules=(rule("sesiones", "POST", r"^/auth/anonymous$", 60, 3),), **kw)
    return TestClient(app)


def test_burst_then_429_with_retry_after():
    c = make_client()
    codes = [c.post("/auth/anonymous", headers={"CF-Connecting-IP": "1.1.1.1"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    r = c.post("/auth/anonymous", headers={"CF-Connecting-IP": "1.1.1.1"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert "Demasiadas" in r.json()["detail"]


def test_limits_are_per_client_and_per_route():
    c = make_client()
    for _ in range(3):
        c.post("/auth/anonymous", headers={"CF-Connecting-IP": "1.1.1.1"})
    assert c.post("/auth/anonymous", headers={"CF-Connecting-IP": "2.2.2.2"}).status_code == 200
    assert c.post("/auth/anonymous", headers={"X-Forwarded-For": "3.3.3.3, 10.0.0.1"}).status_code == 200
    assert all(c.get("/libre").status_code == 200 for _ in range(10))


def test_disabled():
    c = make_client(enabled=False)
    assert all(c.post("/auth/anonymous").status_code == 200 for _ in range(10))
