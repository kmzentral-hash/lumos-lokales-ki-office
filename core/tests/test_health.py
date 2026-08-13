from fastapi import FastAPI
from fastapi.testclient import TestClient

from lumos_core.main import app


def test_health_is_local_and_ready() -> None:
    assert isinstance(app, FastAPI)
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["local_only"] is True
    assert body["version"] == "0.4.0"
    assert body["components"]["retrieval"] == "ready"
    assert body["components"]["search"] == "ready"


def test_root_docs_and_required_routes_are_registered() -> None:
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/api/docs", follow_redirects=False).status_code in {307, 308}

    paths = app.openapi()["paths"]
    assert "get" in paths["/api/v1/health"]
    assert "get" in paths["/api/v1/documents"]
    assert "post" in paths["/api/v1/documents"]
    assert "delete" in paths["/api/v1/documents/{document_id}"]
    assert "post" in paths["/api/v1/search"]
