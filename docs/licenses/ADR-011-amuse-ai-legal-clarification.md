# ADR-011: Rechtliche Klarstellung zu Amuse AI und Lizenzkonforme KI-Engines

**Status:** AKZEPTIERT  
**Datum:** 15. August 2026  

## Kontext

Amuse AI unterliegt der *AmuseAI-License-2.0-Personal-NonCommercial*, welche eine kommerzielle Nutzung oder Bündelung ausschließt. Um LumOS für alle Anwender und Geschäftskunden 100 % kostenfrei und rechtssicher zu halten, muss jede KI-Funktion auf lizenziell uneingeschränkt nutzbaren Open-Source-Komponenten (Apache-2.0 / MIT / CC0) basieren.

## Entscheidung

**Unsere rechtssichere Lösung:** Statt Amuse AI nutzt LumOS für Bild- und Sprachsynthese Apache-2.0- und MIT-lizenzierte Open-Source-Engines (Diffusers, TensorStack SDK & Piper TTS).

**Ergebnis:** Du hast dieselben KI-Funktionen (Text, Bild, Sprache, Formulare), bleibst aber rechtlich 100 % abgesichert, kostenfrei und kommerziell nutzbar.

## Empfohlene & Aktive Modelle

1. **Text LLM:** `Qwen/Qwen2.5-7B-Instruct-GGUF` (Apache-2.0) in `models/Qwen/Qwen2.5-7B-Instruct-GGUF/`
2. **Sprachsynthese:** Piper TTS `de_DE-thorsten-medium` (MIT/CC0)
3. **Bildgenerierung:** Diffusers / TensorStack Engine (Apache-2.0)
