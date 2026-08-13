# LumOS – Lokales KI Office

Entwicklungsstand 0.3.0 des lokalen, quellenbasierten KI-Arbeitszentrums von Studio M 360.

## Aktueller Stand

- Svelte-/TypeScript-Oberfläche im LumOS-Design
- neues LumOS-Logo mit eigenständigem App- und Browser-Symbol
- lokaler FastAPI-Core mit Healthcheck
- lokaler Dokumentimport mit Typprüfung, 25-MB-Limit, SHA-256-Identität und SQLite-Metadaten
- lokale Textextraktion für PDF, DOCX, TXT und Markdown
- abschnittsweise Volltextsuche mit Dokument- und PDF-Seitenangaben
- explizite Kein-Beleg-Antwort statt erfundener Inhalte
- Loopback-Bindung und eingeschränkte CORS-Regel
- automatisierter API-Test
- vorbereitet für Rust Supervisor, Tauri v2, SQLite, Qdrant und llama-server

## Lokal starten

Voraussetzungen: Node.js 22+ und Python 3.12+ mit `uv`.

Terminal 1:

```powershell
cd core
uv sync
uv run uvicorn lumos_core.main:app --host 127.0.0.1 --port 8765
```

Terminal 2:

```powershell
npm install
npm run dev
```

Danach `http://127.0.0.1:1420` öffnen.

## Prüfen

```powershell
npm run check
npm run build
cd core
uv run pytest
uv run ruff check .
```

## Nächster Meilenstein

Lokales, freigegebenes Sprachmodell anbinden und die belegten Fundstellen zu formulierten Antworten zusammenführen.
