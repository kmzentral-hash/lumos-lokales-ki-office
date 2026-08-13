import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from lumos_core.documents import (
    DOCUMENT_DIR,
    _connection,
    calculate_sha256,
    detect_document_kind,
    get_document_extension,
    is_supported_document_extension,
    validate_document_file,
)
from lumos_core.main import app

client = TestClient(app)


def test_openapi_registers_search_as_post_only() -> None:
    schema = client.get("/openapi.json").json()
    assert "post" in schema["paths"]["/api/v1/search"]
    assert "get" in schema["paths"]["/api/v1/search"]
    assert client.get("/api/v1/search", params={"query": "LumOS"}).status_code == 200


def test_import_and_list_document() -> None:
    content = b"LumOS Testwissen"
    response = client.post(
        "/api/v1/documents",
        files={"file": ("wissen.txt", BytesIO(content), "text/plain")},
    )
    assert response.status_code in {200, 201}
    assert response.json()["document"]["name"] == "wissen.txt"

    listing = client.get("/api/v1/documents")
    assert listing.status_code == 200
    assert any(item["name"] == "wissen.txt" for item in listing.json()["documents"])

    document = next(item for item in listing.json()["documents"] if item["name"] == "wissen.txt")
    assert document["extracted_chars"] > 0
    assert document["chunk_count"] > 0
    assert document["status"] == "ready"

    details = client.get(f"/api/v1/documents/{document['id']}")
    assert details.status_code == 200
    assert "LumOS Testwissen" in details.json()["document"]["content"]
    assert details.json()["document"]["chunk_count"] > 0


def test_duplicate_upload_is_counted_once() -> None:
    content = b"Ein Dokument mit stabiler Identitaet"
    upload = {"file": ("einmal.txt", BytesIO(content), "text/plain")}
    first = client.post("/api/v1/documents", files=upload)
    second = client.post(
        "/api/v1/documents",
        files={"file": ("nochmal.txt", BytesIO(content), "text/plain")},
    )

    assert first.status_code in {200, 201}
    assert second.status_code in {200, 201}
    assert second.json()["duplicate"] is True

    listing = client.get("/api/v1/documents").json()["documents"]
    matching = [document for document in listing if document["sha256"] == first.json()["document"]["sha256"]]
    assert len(matching) == 1


def test_listing_dedupes_legacy_duplicate_rows_by_sha() -> None:
    with _connection() as connection:
        digest = "deadbeef" * 8
        base = {
            "name": "altbestand.txt",
            "stored_name": "legacy-a.txt",
            "extension": ".txt",
            "media_type": "text/plain",
            "size": 10,
            "sha256": digest,
            "status": "stored",
            "created_at": "2026-01-01T00:00:00+00:00",
            "extracted_chars": 0,
            "error_message": None,
            "extracted_text": "",
        }
        connection.execute(
            "INSERT OR REPLACE INTO documents "
            "(id,name,stored_name,extension,media_type,size,sha256,status,created_at,"
            "extracted_chars,error_message,extracted_text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-1",
                base["name"],
                base["stored_name"],
                base["extension"],
                base["media_type"],
                base["size"],
                base["sha256"],
                base["status"],
                base["created_at"],
                base["extracted_chars"],
                base["error_message"],
                base["extracted_text"],
            ),
        )
        connection.execute(
            "INSERT OR REPLACE INTO documents "
            "(id,name,stored_name,extension,media_type,size,sha256,status,created_at,"
            "extracted_chars,error_message,extracted_text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "legacy-2",
                base["name"],
                "legacy-b.txt",
                base["extension"],
                base["media_type"],
                base["size"],
                base["sha256"],
                base["status"],
                "2026-01-02T00:00:00+00:00",
                base["extracted_chars"],
                base["error_message"],
                base["extracted_text"],
            ),
        )

    listing = client.get("/api/v1/documents")
    assert listing.status_code == 200
    matches = [document for document in listing.json()["documents"] if document["sha256"] == digest]
    assert len(matches) == 1


def test_delete_document_removes_metadata_and_search_chunks() -> None:
    content = b"Dieses Wissen soll nach dem Loeschen verschwinden: Silberkompass."
    uploaded = client.post(
        "/api/v1/documents",
        files={"file": ("loeschen.txt", BytesIO(content), "text/plain")},
    ).json()["document"]

    with _connection() as connection:
        stored_name = connection.execute(
            "SELECT stored_name FROM documents WHERE id=?", (uploaded["id"],)
        ).fetchone()["stored_name"]
        assert connection.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE document_id=?", (uploaded["id"],)
        ).fetchone()[0] > 0
    stored_file = DOCUMENT_DIR / stored_name
    assert stored_file.exists()

    deleted = client.delete(f"/api/v1/documents/{uploaded['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    listing = client.get("/api/v1/documents").json()["documents"]
    assert all(document["id"] != uploaded["id"] for document in listing)
    assert not stored_file.exists()
    with _connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM documents WHERE id=?", (uploaded["id"],)
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE document_id=?", (uploaded["id"],)
        ).fetchone()[0] == 0
    search = client.post("/api/v1/search", json={"query": "Silberkompass"})
    assert all(hit["document_id"] != uploaded["id"] for hit in search.json()["hits"])
    missing = client.get(f"/api/v1/documents/{uploaded['id']}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Dokument wurde nicht gefunden."


def test_search_returns_local_evidence_and_no_evidence() -> None:
    content = b"Die Nordsternfreigabe gilt ausschliesslich fuer das LumOS Projekt Delta."
    response = client.post(
        "/api/v1/documents",
        files={"file": ("nordstern.txt", BytesIO(content), "text/plain")},
    )
    assert response.status_code in {200, 201}

    found = client.post(
        "/api/v1/search", json={"query": "Nordsternfreigabe Projekt Delta", "limit": 5}
    )
    assert found.status_code == 200
    assert found.json()["evidence_found"] is True
    assert "Nordsternfreigabe" in found.json()["answer"]
    assert found.json()["hits"][0]["document_name"] == "nordstern.txt"

    missing = client.post("/api/v1/search", json={"query": "Quantenbanane Zebraturm"})
    assert missing.status_code == 200
    assert missing.json()["evidence_found"] is False


def test_rejects_disguised_pdf() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("falsch.pdf", BytesIO(b"kein PDF"), "application/pdf")},
    )
    assert response.status_code == 415


def test_image_is_not_indexed_as_text() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("bild.png", BytesIO(b"\x89PNG\r\n\x1a\nimage"), "image/png")},
    )
    assert response.status_code in {200, 201}
    document = response.json()["document"]
    assert document["status"] == "unsupported"
    assert document["extracted_chars"] == 0
    assert document["chunk_count"] == 0
    assert "OCR" in document["error_message"]


def test_reprocess_rebuilds_ready_document() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("erneut.md", BytesIO(b"# Einzigartige Wiederverarbeitung"), "text/markdown")},
    )
    document_id = response.json()["document"]["id"]
    processed = client.post(f"/api/v1/documents/{document_id}/process")
    assert processed.status_code == 200
    assert processed.json()["document"]["status"] == "ready"
    assert processed.json()["document"]["extracted_chars"] > 0


def test_txt_upload_to_search_integration() -> None:
    proverb = "Morgenstund hat Gold im Mund und der Bernsteinfalke wacht darüber."
    upload = client.post(
        "/api/v1/documents",
        files={"file": ("sprichwort.txt", BytesIO(proverb.encode()), "text/plain")},
    )
    assert upload.status_code == 201
    document = upload.json()["document"]
    assert document["status"] == "ready"
    assert document["character_count"] > 0
    assert document["chunk_count"] > 0

    details = client.get(f"/api/v1/documents/{document['id']}")
    assert details.status_code == 200
    assert proverb in details.json()["document"]["content"]
    with _connection() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE document_id=?", (document["id"],)
        ).fetchone()[0] > 0

    search = client.post(
        "/api/v1/search", json={"query": "Bernsteinfalke Morgenstund", "limit": 5}
    )
    assert search.status_code == 200
    assert search.json()["evidence_found"] is True
    hit = search.json()["hits"][0]
    assert hit["document_name"] == "sprichwort.txt"
    assert "Bernsteinfalke" in hit["excerpt"]


def test_accepts_supported_text_document() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("test.txt", BytesIO(b"Inhalt eines unterstuetzten Textdokuments."), "text/plain")},
    )
    assert response.status_code in {200, 201}
    assert response.json()["document"]["name"] == "test.txt"
    assert response.json()["document"]["status"] == "ready"


def test_rejects_unsupported_extension() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("skript.exe", BytesIO(b"MZ\x90\x00"), "application/x-msdownload")},
    )
    assert response.status_code == 415
    assert "nicht freigegeben" in response.json()["detail"]


def test_rejects_fake_pdf_with_wrong_magic_number() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("schadcode.pdf", BytesIO(b"Das ist kein PDF Header"), "application/pdf")},
    )
    assert response.status_code == 415
    assert "Dateiendung und Dateiinhalt stimmen nicht" in response.json()["detail"]


def test_accepts_realistic_pdf_header() -> None:
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    response = client.post(
        "/api/v1/documents",
        files={"file": ("minimal.pdf", BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code in {200, 201}
    assert response.json()["document"]["name"] == "minimal.pdf"


def test_detects_duplicate_by_sha256() -> None:
    content = b"Stabile SHA256 Erkennung fuer Duplikate"
    first = client.post(
        "/api/v1/documents",
        files={"file": ("orig.txt", BytesIO(content), "text/plain")},
    )
    second = client.post(
        "/api/v1/documents",
        files={"file": ("kopie.txt", BytesIO(content), "text/plain")},
    )
    assert first.status_code in {200, 201}
    assert second.status_code in {200, 201}
    assert second.json()["duplicate"] is True
    assert second.json()["document"]["sha256"] == first.json()["document"]["sha256"]


def test_rejects_oversized_document() -> None:
    large_content = b"x" * (25 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/documents",
        files={"file": ("gross.txt", BytesIO(large_content), "text/plain")},
    )
    assert response.status_code == 413
    assert "überschreitet das Limit" in response.json()["detail"]


def test_does_not_modify_original_file(tmp_path: Path) -> None:
    sample = tmp_path / "original.txt"
    sample.write_bytes(b"Originaler unveraenderter Dateiinhalt.")
    original_bytes = sample.read_bytes()

    response = client.post(
        "/api/v1/documents",
        files={"file": ("original.txt", BytesIO(original_bytes), "text/plain")},
    )
    assert response.status_code in {200, 201}
    assert sample.read_bytes() == original_bytes


def test_accepts_markdown_document() -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("notizen.markdown", BytesIO(b"# Markdown Notizen"), "text/markdown")},
    )
    assert response.status_code in {200, 201}
    assert response.json()["document"]["name"] == "notizen.markdown"
    assert response.json()["document"]["status"] == "ready"


def test_accepts_minimal_docx_zip() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
    content = buffer.getvalue()

    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "minimal.docx",
                BytesIO(content),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code in {200, 201}
    assert response.json()["document"]["name"] == "minimal.docx"


def test_rejects_fake_docx_zip_without_content_types() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("archiv.txt", "kein docx")
    content = buffer.getvalue()

    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "fake.docx",
                BytesIO(content),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 415
    assert "Dateiendung und Dateiinhalt stimmen nicht" in response.json()["detail"]


def test_validate_document_file_helpers(tmp_path: Path) -> None:
    sample = tmp_path / "valid.txt"
    sample.write_bytes(b"Valider Dateiinhalt")
    assert get_document_extension(sample) == ".txt"
    assert is_supported_document_extension(sample) is True
    assert detect_document_kind(sample) == "text"
    assert calculate_sha256(sample) is not None

    res = validate_document_file(sample, allowed_root=tmp_path)
    assert res.status == "accepted"
    assert res.file_type == "text"
    assert res.reason is None


