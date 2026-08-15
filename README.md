# LumOS Lokal Office

Das lokale, sichere KI-Arbeitszentrum für Ihr Büro – 100 % lokal, datenschutzkonform und kommerziell frei nutzbar.

---

## ⚖️ Rechtssicherheit & Freie Kommerzielle Nutzung (ADR-011)

**Unsere rechtssichere Lösung:** Statt Amuse AI nutzt LumOS für Bild- und Sprachsynthese Apache-2.0- und MIT-lizenzierte Open-Source-Engines (Diffusers, TensorStack SDK & Piper TTS).

**Ergebnis:** Du hast dieselben KI-Funktionen (Text, Bild, Sprache, Formulare), bleibst aber rechtlich 100 % abgesichert, kostenfrei und kommerziell nutzbar.

---

## 🧠 Empfohlene & Aktive Modelle (in `models/`)

1. **Text LLM (RAG & Chat):** `Qwen2.5-7B-Instruct-GGUF` (`qwen2.5-7b-instruct-q4_k_m.gguf`)
   * **Pfad:** `models/Qwen/Qwen2.5-7B-Instruct-GGUF/`
   * **Lizenz:** Apache-2.0 (100 % kommerziell frei nutzbar)
   * **Leistung:** Exzellentes Deutschverständnis, präzise Befolgung von Befehlen und hohe RAG-Genauigkeit.
2. **Sprachsynthese (TTS):** `de_DE-thorsten-medium` (Piper TTS Engine)
   * **Lizenz:** MIT / CC0 (100 % kommerziell frei nutzbar)
3. **Bildgenerierung:** Headless Diffusers & TensorStack SDK Engine (FLUX.1-schnell / SDXL)
   * **Lizenz:** Apache-2.0 / MIT (100 % kommerziell frei nutzbar)

---

## 🚀 1-Click Start

Doppelklick auf `start.bat` in der Projekt-Wurzel:
* Startet automatisch das FastAPI Backend (`127.0.0.1:8765`).
* Erkennt das lokale GGUF-Modell und startet `llama-server.exe` (`127.0.0.1:8080`).
* Startet das Svelte Frontend UI (`127.0.0.1:1420`).
* Öffnet automatisch den Standardbrowser auf `http://127.0.0.1:1420`.
