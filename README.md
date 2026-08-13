# LumOS – Lokales KI Office

Entwicklungsstand 0.5.0 des lokalen, quellenbasierten KI-Arbeitszentrums von Studio M 360.

## Aktueller Stand

- Svelte-/TypeScript-Oberfläche im LumOS-Design
- neues LumOS-Logo mit eigenständigem App- und Browser-Symbol
- lokaler FastAPI-Core mit Healthcheck
- lokaler Dokumentimport mit Typprüfung, 25-MB-Limit, SHA-256-Identität und SQLite-Metadaten
- lokale Textextraktion für PDF, DOCX, TXT und Markdown
- abschnittsweise Volltextsuche mit Dokument- und PDF-Seitenangaben
- lokales Control Center mit Backend-, Such- und Dokumentstatus
- Dokumentverwaltung mit Details, Neuverarbeitung, Zeichen- und Chunk-Zahlen
- optionale lokale KI-Antworten ueber eine OpenAI-kompatible llama-server API
- quellengebundener Antwortmodus mit dokumentierter Fundstellenzuordnung
- explizite Kein-Beleg-Antwort statt erfundener Inhalte
- Loopback-Bindung und eingeschränkte CORS-Regel
- automatisierter API-Test
- vorbereitet für Rust Supervisor, Tauri v2, SQLite, Qdrant und llama-server

## Lokal starten

Voraussetzungen: Node.js 22+ und Python 3.12+ mit `uv`.

Komfortstart unter Windows:

```powershell
.\start-lumos.bat
```

Selbstheilender Start mit Portpruefung, Dependency-Sync und API-Checks:

```powershell
.\heal-lumos.bat
```

Direkt per PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\heal-lumos.ps1 -Restart
```

Alternativ getrennt starten:

```powershell
.\start-backend.bat
.\start-frontend.bat
```

Manueller Start:

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

Der Backend-Core läuft auf `http://127.0.0.1:8765`; die API-Dokumentation ist unter `http://127.0.0.1:8765/docs` erreichbar. Das Frontend zeigt "Core bereit" nur, wenn Healthcheck und `POST /api/v1/search` verfügbar sind.

## Lokale KI mit llama-server

llama-server ist optional. LumOS funktioniert ohne laufendes lokales Modell weiterhin als Dokumentverwaltung und RAG-Quellensuche. Es wird kein Modell automatisch heruntergeladen, gebundelt oder gestartet.

LumOS erwartet eine lokale OpenAI-kompatible API, standardmaessig:

```text
http://127.0.0.1:8080/v1
```

Konfiguration ueber Umgebungsvariablen:

```powershell
$env:LUMOS_LLM_BASE_URL="http://127.0.0.1:8080/v1"
$env:LUMOS_LLM_MODEL="<lokal-verfuegbares-modell>"
$env:LUMOS_LLM_TIMEOUT_SECONDS="30"
# optional fuer kompatible lokale Provider:
$env:LUMOS_LLM_API_KEY=""
```

Startbeispiel fuer einen bereits installierten llama-server, ohne Modellvorgabe:

```powershell
llama-server --host 127.0.0.1 --port 8080 -m "<pfad-zum-lokal-vorhandenen-modell>"
```

Sicherheitsregeln:

- Standardmaessig sind nur Loopback-Adressen wie `127.0.0.1` oder `localhost` als LLM-Base-URL erlaubt.
- Dokumentinhalte werden nur an den lokal konfigurierten Provider gesendet.
- Cloud-APIs sind nicht vorgesehen.
- Die Modell-Allowlist ist lokal: nur das Modell in `LUMOS_LLM_MODEL` wird angefragt.
- Anweisungen innerhalb von Dokumenten gelten als nicht vertrauenswuerdig und duerfen den System-Prompt nicht ueberschreiben.

Fehlersuche:

- `GET /api/v1/llm/status` zeigt Konfiguration, Erreichbarkeit und letzte LLM-Fehlermeldung.
- Wenn llama-server nicht laeuft, bleibt `POST /api/v1/search` nutzbar.
- Wenn `LUMOS_LLM_MODEL` fehlt, zeigt LumOS "nicht konfiguriert".
- Wenn `LUMOS_LLM_BASE_URL` nicht lokal ist, verweigert LumOS die Generierung.

## Prüfen

```powershell
npm run check
npm run build
cd core
uv run pytest
uv run ruff check .
```

## Nächster Meilenstein

Lokale Modellverwaltung und ein Windows-Supervisor fuer den kontrollierten llama-server Start.
