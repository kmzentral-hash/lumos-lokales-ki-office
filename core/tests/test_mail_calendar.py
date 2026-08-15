from pathlib import Path

from fastapi.testclient import TestClient

from lumos_core.main import app

client = TestClient(app)


def test_create_email_draft() -> None:
    payload = {
        "recipient_email": "max@musterfirma.de",
        "subject": "Angebot fuer LumOS Lokal Office Software",
        "body_text": "Sehr geehrter Herr Muster,\n\nanbei erhalten Sie unser Angebot.",
        "sender_name": "Studio M 360",
    }
    response = client.post("/api/v1/mail-calendar/email/draft", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "mailto:max%40musterfirma.de" in data["mailto_url"]
    assert Path(data["eml_file_path"]).exists()
    assert ".eml" in data["filename"]


def test_create_calendar_draft() -> None:
    payload = {
        "title": "LumOS Produkt-Präsentation",
        "location": "Online Meeting",
        "description": "Vorführung der lokalen KI-Funktionen.",
        "start_time_iso": "2026-08-20T10:00:00Z",
        "duration_minutes": 60,
        "attendee_email": "max@musterfirma.de",
    }
    response = client.post("/api/v1/mail-calendar/calendar/draft", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert Path(data["ics_file_path"]).exists()
    assert ".ics" in data["filename"]
