from pathlib import Path

from fastapi.testclient import TestClient

from lumos_core.main import app

client = TestClient(app)


def test_generate_local_image() -> None:
    payload = {
        "prompt": "Ein modernes Firmenlogo fuer LumOS Lokal Office",
        "width": 512,
        "height": 512,
        "style": "business",
        "custom_filename": "test_logo_lumos",
    }
    response = client.post("/api/v1/media/image/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "test_logo_lumos.png" in data["filename"]
    assert Path(data["image_path"]).exists()
    assert Path(data["image_path"]).stat().st_size > 500
    assert "Apache-2.0" in data["license_status"]


def test_generate_local_tts() -> None:
    payload = {
        "text": "Dies ist ein Sprachsynthese-Test fuer LumOS Lokal Office.",
        "voice": "de_DE-thorsten-medium",
        "speed": 1.0,
        "custom_filename": "test_audio_lumos",
    }
    response = client.post("/api/v1/media/tts/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "test_audio_lumos.wav" in data["filename"]
    assert Path(data["audio_path"]).exists()
    assert Path(data["audio_path"]).stat().st_size > 500
    assert data["duration_seconds"] > 0


def test_list_generated_media() -> None:
    response = client.get("/api/v1/media/list")
    assert response.status_code == 200
    data = response.json()
    assert "media_dir" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data["count"] >= 2
