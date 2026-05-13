"""Smoke: /health returns 200."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health():
    from chainpulse.backend.main import app

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
