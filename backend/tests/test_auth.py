from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import auth


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router)

    @app.get("/protected")
    def protected(_: None = Depends(auth.require_auth)):
        return {"ok": True}

    return app


def test_login_with_wrong_password_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "correct-horse")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    client = TestClient(_build_app())

    res = client.post("/api/auth/login", json={"password": "wrong"})
    assert res.status_code == 401


def test_login_then_access_protected_route(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "correct-horse")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    client = TestClient(_build_app())

    login_res = client.post("/api/auth/login", json={"password": "correct-horse"})
    assert login_res.status_code == 200
    assert login_res.json() == {"authenticated": True}

    protected_res = client.get("/protected")
    assert protected_res.status_code == 200


def test_protected_route_without_session_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "correct-horse")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    client = TestClient(_build_app())

    res = client.get("/protected")
    assert res.status_code == 401


def test_logout_clears_session(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "correct-horse")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    client = TestClient(_build_app())

    client.post("/api/auth/login", json={"password": "correct-horse"})
    assert client.get("/protected").status_code == 200

    client.post("/api/auth/logout")
    assert client.get("/protected").status_code == 401
