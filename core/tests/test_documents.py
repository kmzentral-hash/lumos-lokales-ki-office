from io import BytesIO

from fastapi.testclient import TestClient

from lumos_core.documents import DOCUMENT_DIR, _connection
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
