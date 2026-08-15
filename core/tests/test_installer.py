from pathlib import Path

from fastapi.testclient import TestClient

from lumos_core.main import app

client = TestClient(app)


def test_check_installer_preflight() -> None:
    response = client.get("/api/v1/installer/preflight")
    assert response.status_code == 200
    data = response.json()
    assert "is_windows_11" in data
    assert "ram_gb" in data
    assert data["ram_ok"] is True
    assert data["disk_ok"] is True
    assert data["setup_ready"] is True


def test_build_installer_manifest() -> None:
    response = client.post("/api/v1/installer/build-manifest")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "LumOS Core"
    assert data["publisher"] == "Studio M 360"
    assert Path(data["iss_script_path"]).exists()
    assert Path(data["silent_script_path"]).exists()
    assert "lumos-setup.iss" in data["iss_script_path"]
