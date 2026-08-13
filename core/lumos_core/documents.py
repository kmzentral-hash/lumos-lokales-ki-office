from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from docx import Document
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pypdf import PdfReader

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DOCUMENT_DIR = DATA_DIR / "documents"
DATABASE_PATH = DATA_DIR / "lumos.db"
MAX_FILE_SIZE = 25 * 1024 * 1024
TEXT_TYPES = {".pdf", ".docx", ".txt", ".md"}
IMAGE_TYPES = {".png", ".jpg", ".jpeg"}
ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, stored_name TEXT NOT NULL,
            extension TEXT NOT NULL, media_type TEXT NOT NULL, size INTEGER NOT NULL,
            sha256 TEXT NOT NULL UNIQUE, status TEXT NOT NULL, created_at TEXT NOT NULL
        )
        """
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
    if "extracted_chars" not in columns:
        connection.execute(
            "ALTER TABLE documents ADD COLUMN extracted_chars INTEGER NOT NULL DEFAULT 0"
        )
    if "error_message" not in columns:
        connection.execute("ALTER TABLE documents ADD COLUMN error_message TEXT")
    if "extracted_text" not in columns:
        connection.execute("ALTER TABLE documents ADD COLUMN extracted_text TEXT NOT NULL DEFAULT ''")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL, chunk_index INTEGER NOT NULL,
            page INTEGER, section TEXT NOT NULL, content TEXT NOT NULL,
            FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id)"
    )
    connection.execute(
        "UPDATE documents SET status = CASE "
        "WHEN extension IN ('.png', '.jpg', '.jpeg') THEN 'unsupported' "
        "WHEN extracted_chars > 0 THEN 'ready' ELSE 'stored' END "
        "WHERE status NOT IN ('stored', 'processing', 'ready', 'failed', 'unsupported')"
    )
    connection.commit()
    return connection


def _safe_name(filename: str) -> str:
    basename = Path(filename).name.strip()
    return re.sub(r"[^\w.() -]", "_", basename, flags=re.UNICODE)[:180] or "dokument"


def _valid_signature(extension: str, content: bytes) -> bool:
    if extension == ".pdf":
        return content.startswith(b"%PDF-")
    if extension == ".docx":
        return content.startswith(b"PK\x03\x04")
    if extension == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if extension in {".txt", ".md"}:
        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    return False


def _chunk_count(connection: sqlite3.Connection, document_id: str) -> int:
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE document_id=?", (document_id,)
        ).fetchone()[0]
    )


def _dedupe_rows_by_sha(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    # Keep the newest entry per SHA-256, preserving list order.
    seen: set[str] = set()
    deduped: list[sqlite3.Row] = []
    for row in rows:
        digest = str(row["sha256"])
        if digest in seen:
            continue
        seen.add(digest)
        deduped.append(row)
    return deduped


def _as_dict(
    row: sqlite3.Row, connection: sqlite3.Connection, include_content: bool = False
) -> dict[str, object]:
    result: dict[str, object] = {
        "id": row["id"],
        "name": row["name"],
        "type": row["extension"].removeprefix(".").upper(),
        "media_type": row["media_type"],
        "size": row["size"],
        "sha256": row["sha256"],
        "status": row["status"],
        "extracted_chars": row["extracted_chars"] or 0,
        "character_count": row["extracted_chars"] or 0,
        "chunk_count": _chunk_count(connection, row["id"]),
        "error_message": row["error_message"],
        "created_at": row["created_at"],
    }
    if include_content:
        result["content"] = row["extracted_text"] or ""
    return result


def _extract_segments(extension: str, content: bytes) -> list[tuple[int | None, str, str]]:
    if extension in {".txt", ".md"}:
        return [(None, "Gesamtdokument", content.decode("utf-8"))]
    if extension == ".pdf":
        reader = PdfReader(BytesIO(content))
        return [
            (number, f"Seite {number}", page.extract_text() or "")
            for number, page in enumerate(reader.pages, start=1)
        ]
    if extension == ".docx":
        document = Document(BytesIO(content))
        return [
            (None, f"Abschnitt {number}", paragraph.text)
            for number, paragraph in enumerate(document.paragraphs, start=1)
            if paragraph.text.strip()
        ]
    return []


def _chunks(segments: list[tuple[int | None, str, str]]) -> list[tuple[int | None, str, str]]:
    result: list[tuple[int | None, str, str]] = []
    for page, section, raw_text in segments:
        text = re.sub(r"\s+", " ", raw_text).strip()
        start = 0
        while start < len(text):
            end = min(start + 1400, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + 700, end)
                if boundary > start:
                    end = boundary
            chunk = text[start:end].strip()
            if chunk:
                result.append((page, section, chunk))
            if end >= len(text):
                break
            start = max(end - 180, start + 1)
    return result


def _process_document(connection: sqlite3.Connection, row: sqlite3.Row) -> sqlite3.Row:
    document_id = row["id"]
    extension = row["extension"]
    if extension in IMAGE_TYPES:
        connection.execute(
            "UPDATE documents SET status='unsupported', extracted_chars=0, extracted_text='', "
            "error_message=? WHERE id=?",
            ("Für Bilder ist noch keine OCR konfiguriert.", document_id),
        )
        connection.execute("DELETE FROM document_chunks WHERE document_id=?", (document_id,))
        return connection.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()

    connection.execute(
        "UPDATE documents SET status='processing', error_message=NULL WHERE id=?", (document_id,)
    )
    try:
        content = (DOCUMENT_DIR / row["stored_name"]).read_bytes()
        segments = _extract_segments(extension, content)
        extracted_text = "\n".join(text.strip() for _, _, text in segments if text.strip())
        chunks = _chunks(segments)
        connection.execute("DELETE FROM document_chunks WHERE document_id=?", (document_id,))
        for index, (page, section, chunk) in enumerate(chunks):
            connection.execute(
                "INSERT INTO document_chunks "
                "(id, document_id, chunk_index, page, section, content) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid4()), document_id, index, page, section, chunk),
            )
        if extracted_text:
            connection.execute(
                "UPDATE documents SET status='ready', extracted_chars=?, extracted_text=?, "
                "error_message=NULL "
                "WHERE id=?",
                (len(extracted_text), extracted_text, document_id),
            )
        else:
            connection.execute(
                "UPDATE documents SET status='failed', extracted_chars=0, extracted_text='', "
                "error_message=? WHERE id=?",
                ("In diesem Dokument wurde kein lesbarer Text gefunden.", document_id),
            )
    except Exception as exc:  # noqa: BLE001 - parser failures must become persisted document errors
        connection.execute("DELETE FROM document_chunks WHERE document_id=?", (document_id,))
        connection.execute(
            "UPDATE documents SET status='failed', extracted_chars=0, extracted_text='', "
            "error_message=? WHERE id=?",
            (f"Textextraktion fehlgeschlagen: {exc}", document_id),
        )
    return connection.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()


@router.get("")
async def list_documents() -> dict[str, object]:
    with _connection() as connection:
        rows = connection.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        unique_rows = _dedupe_rows_by_sha(rows)
        documents = [_as_dict(row, connection) for row in unique_rows]
    return {"documents": documents, "count": len(unique_rows)}


@router.get("/{document_id}")
async def get_document(document_id: str) -> dict[str, object]:
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM documents WHERE id=?",
            (document_id,),
        ).fetchone()
        document = _as_dict(row, connection, include_content=True) if row is not None else None
    if row is None:
        raise HTTPException(status_code=404, detail="Dokument wurde nicht gefunden.")
    return {"document": document}


@router.post("/{document_id}/process")
async def reprocess_document(document_id: str) -> dict[str, object]:
    with _connection() as connection:
        row = connection.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Dokument wurde nicht gefunden.")
        processed = _process_document(connection, row)
        document = _as_dict(processed, connection)
    return {"document": document}


@router.delete("/{document_id}")
async def delete_document(document_id: str) -> dict[str, object]:
    with _connection() as connection:
        row = connection.execute(
            "SELECT id, stored_name FROM documents WHERE id=?", (document_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Dokument wurde nicht gefunden.")
        stored_file = DOCUMENT_DIR / row["stored_name"]
        try:
            stored_file.unlink(missing_ok=True)
        except OSError as exc:
            raise HTTPException(
                status_code=500, detail=f"Gespeicherte Datei konnte nicht entfernt werden: {exc}"
            ) from exc
        connection.execute("DELETE FROM documents WHERE id=?", (document_id,))
    return {"deleted": True, "id": document_id}


@router.post("", status_code=status.HTTP_201_CREATED)
async def import_document(file: Annotated[UploadFile, File()]) -> dict[str, object]:
    original_name = _safe_name(file.filename or "dokument")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Dieser Dateityp ist nicht freigegeben.")
    content = await file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Die Datei ist leer.")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Die Datei überschreitet das Limit von 25 MB.")
    if not _valid_signature(extension, content):
        raise HTTPException(status_code=415, detail="Dateiendung und Dateiinhalt stimmen nicht überein.")

    digest = hashlib.sha256(content).hexdigest()
    with _connection() as connection:
        existing = connection.execute(
            "SELECT * FROM documents WHERE sha256=? ORDER BY created_at DESC LIMIT 1",
            (digest,),
        ).fetchone()
        if existing:
            if existing["extension"] in TEXT_TYPES and not existing["extracted_text"]:
                existing = _process_document(connection, existing)
            return {"document": _as_dict(existing, connection), "duplicate": True}
        document_id = str(uuid4())
        stored_name = f"{document_id}{extension}"
        DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)
        (DOCUMENT_DIR / stored_name).write_bytes(content)
        connection.execute(
            "INSERT INTO documents "
            "(id,name,stored_name,extension,media_type,size,sha256,status,created_at,"
            "extracted_chars,error_message,extracted_text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (document_id, original_name, stored_name, extension, ALLOWED_TYPES[extension],
             len(content), digest, "stored", datetime.now(UTC).isoformat(), 0, None, ""),
        )
        row = connection.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        processed = _process_document(connection, row)
        document = _as_dict(processed, connection)
    return {"document": document, "duplicate": False}
