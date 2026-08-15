from fastapi.testclient import TestClient

from lumos_core.main import app

client = TestClient(app)


def test_get_hardware_info() -> None:
    response = client.get("/api/v1/system/hardware")
    assert response.status_code == 200
    data = response.json()
    assert "os_name" in data
    assert "cpu_cores_logical" in data
    assert data["cpu_cores_logical"] > 0
    assert data["memory_total_gb"] > 0
    assert "gpu_acceleration" in data
    assert "recommended_profile" in data
    assert data["status"] == "ok"


def test_scan_installed_models() -> None:
    response = client.get("/api/v1/system/models")
    assert response.status_code == 200
    data = response.json()
    assert "models_dir" in data
    assert "installed_models" in data
    assert isinstance(data["installed_models"], list)
    assert "count" in data


def test_get_sbom() -> None:
    response = client.get("/api/v1/system/sbom")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] is not None
    assert "components" in data
    assert len(data["components"]) >= 5

    comp_names = [c["name"] for c in data["components"]]
    assert any("FastAPI" in name for name in comp_names)
    assert any("llama-server" in name for name in comp_names)
    assert any("Qwen2.5" in name for name in comp_names)
