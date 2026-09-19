import pytest
from fastapi.testclient import TestClient
from app.config import Settings, ROOT
from app.main import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(db_path=tmp_path / "test.db"))


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session(client):
    response = client.post("/api/sessions", json={})
    assert response.status_code == 201
    return response.json()


def turn(client, s, text="", action="message", **extra):
    r = client.post(
        f'/api/sessions/{s["id"]}/turn',
        json={
            "action": action,
            "text": text,
            "expected_revision": s["revision"],
            **extra,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()
