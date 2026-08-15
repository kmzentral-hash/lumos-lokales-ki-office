from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from lumos_core.export import LetterExportRequest, create_letter_docx, create_letter_pdf
from lumos_core.main import app

client = TestClient(app)


def test_preview_letter_export() -> None:
    payload = {
        "sender_name": "Studio M 360 GmbH",
        "sender_address": "Musterstraße 1, 10115 Berlin",
        "recipient_name": "Max Mustermann",
        "recipient_company": "Musterfirma AG",
        "recipient_address": "Hauptstraße 45, 80331 München",
        "subject": "Test Angebot",
        "salutation": "Sehr geehrter Herr Mustermann,",
        "body_text": "Dies ist ein Testtext für den Geschäftsbrief.\nZweiter Absatz mit Details.",
        "closing": "Mit freundlichen Grüßen",
        "signoff_name": "Kevin Miller",
    }
    response = client.post("/api/v1/export/letter/preview", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Studio M 360 GmbH" in data["formatted_preview_html"]
    assert "Musterfirma AG" in data["formatted_preview_html"]
    assert "Test Angebot" in data["formatted_preview_html"]
    assert len(data["body_paragraphs"]) == 2
    assert data["word_count"] > 0


def test_generate_letter_export_requires_human_approval() -> None:
    payload = {
        "subject": "Ohne Freigabe",
        "body_text": "Inhalt ohne Freigabe",
        "human_approved": False,
    }
    response = client.post("/api/v1/export/letter/generate", json=payload)
    assert response.status_code == 400
    assert "ausdrückliche menschliche Freigabe" in response.json()["detail"]


def test_generate_letter_export_creates_valid_docx_and_pdf() -> None:
    payload = {
        "sender_name": "Studio M 360 GmbH",
        "recipient_name": "Erika Mustermann",
        "subject": "Freigegebener Geschäftsbrief Test",
        "body_text": "Absatz 1 des Geschäftsbriefs.\nAbsatz 2 des Geschäftsbriefs.",
        "export_formats": ["docx", "pdf"],
        "custom_filename": "test_brief_freigabe",
        "human_approved": True,
    }
    response = client.post("/api/v1/export/letter/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["human_approved"] is True
    assert data["docx_path"] is not None
    assert data["pdf_path"] is not None

    docx_path = Path(data["docx_path"])
    pdf_path = Path(data["pdf_path"])

    assert docx_path.exists()
    assert pdf_path.exists()
    assert docx_path.stat().st_size > 0
    assert pdf_path.stat().st_size > 0

    # Read back PDF with PyPDF to verify readable content
    reader = PdfReader(pdf_path)
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Freigegebener Geschäftsbrief Test" in text
    assert "Studio M 360 GmbH" in text
    assert "Erika Mustermann" in text


def test_direct_docx_and_pdf_generators(tmp_path: Path) -> None:
    req = LetterExportRequest(
        sender_name="Direkt Test Absender",
        recipient_name="Direkt Test Empfänger",
        subject="Direkttest Betreff",
        body_text="Testinhalt direkt generiert.",
        human_approved=True,
    )
    docx_file = tmp_path / "direkt.docx"
    pdf_file = tmp_path / "direkt.pdf"

    create_letter_docx(req, docx_file)
    create_letter_pdf(req, pdf_file)

    assert docx_file.exists()
    assert pdf_file.exists()
    assert docx_file.stat().st_size > 500
    assert pdf_file.stat().st_size > 500
