export type HealthResponse = {
  status: 'ok';
  service: string;
  version: string;
  local_only: boolean;
  components: Record<string, string>;
};

export type DocumentItem = {
  id: string;
  name: string;
  type: string;
  media_type: string;
  size: number;
  sha256: string;
  status: 'stored' | 'processing' | 'ready' | 'failed' | 'unsupported';
  extracted_chars?: number;
  character_count?: number;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  content?: string;
};

export type SearchHit = { chunk_id: string; document_id: string; document_name: string; page: number | null; section: string; excerpt: string; score: number; };
export type SearchResponse = { query: string; evidence_found: boolean; answer: string | null; hits: SearchHit[]; count: number; };
export type LlmStatusResponse = {
  configured: boolean;
  base_url: string;
  model: string | null;
  loopback_only: boolean;
  reachable: boolean;
  generation_available: boolean;
  last_error: string | null;
};
export type RagAnswerResponse = {
  answer: string;
  sources: SearchHit[];
  model: string | null;
  grounded: boolean;
  insufficient_evidence: boolean;
  llm_available?: boolean;
  warning: string | null;
};

async function responseError(response: Response, fallback: string): Promise<Error> {
  try {
    const result = await response.json() as { detail?: string };
    const detail = result.detail || fallback;
    if (/not found/i.test(detail)) return new Error('Die angefragte Funktion oder Ressource ist nicht erreichbar.');
    return new Error(detail);
  } catch {
    return new Error(fallback);
  }
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
const apiUrl = (path: string) => `${API_BASE_URL}${path}`;

export async function fetchHealth(): Promise<HealthResponse> {
  let response: Response;
  try {
    response = await fetch(apiUrl('/api/v1/health'));
  } catch {
    throw new Error('Backend nicht erreichbar. Bitte starte den LumOS Core.');
  }
  if (!response.ok) throw new Error('Backend nicht erreichbar. Der Healthcheck antwortet nicht erfolgreich.');
  return response.json() as Promise<HealthResponse>;
}

export async function fetchDocuments(): Promise<DocumentItem[]> {
  let response: Response;
  try {
    response = await fetch(apiUrl('/api/v1/documents'));
  } catch {
    throw new Error('Backend nicht erreichbar. Die Dokumentliste konnte nicht geladen werden.');
  }
  if (!response.ok) throw new Error('Dokumentverwaltung nicht erreichbar.');
  const result = await response.json() as { documents: DocumentItem[] };
  return Array.from(
    new Map(result.documents.map((document) => [document.sha256, document])).values()
  );
}

export async function uploadDocument(file: File): Promise<{ document: DocumentItem; duplicate: boolean }> {
  const body = new FormData();
  body.append('file', file);
  let response: Response;
  try {
    response = await fetch(apiUrl('/api/v1/documents'), { method: 'POST', body });
  } catch {
    throw new Error('Backend nicht erreichbar. Das Dokument wurde nicht importiert.');
  }
  const result = await response.json() as { document: DocumentItem; duplicate: boolean; detail?: string };
  if (!response.ok) throw new Error(result.detail || `Import fehlgeschlagen: ${response.status}`);
  return result;
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(apiUrl(`/api/v1/documents/${encodeURIComponent(documentId)}`), {
    method: 'DELETE'
  });
  if (!response.ok) throw await responseError(response, `Löschen fehlgeschlagen: ${response.status}`);
}

export async function fetchDocument(documentId: string): Promise<DocumentItem> {
  const response = await fetch(apiUrl(`/api/v1/documents/${encodeURIComponent(documentId)}`));
  if (!response.ok) throw await responseError(response, `Details konnten nicht geladen werden: ${response.status}`);
  const result = await response.json() as { document: DocumentItem };
  return result.document;
}

export async function reprocessDocument(documentId: string): Promise<DocumentItem> {
  const response = await fetch(apiUrl(`/api/v1/documents/${encodeURIComponent(documentId)}/process`), {
    method: 'POST'
  });
  if (!response.ok) throw await responseError(response, `Neuverarbeitung fehlgeschlagen: ${response.status}`);
  const result = await response.json() as { document: DocumentItem };
  return result.document;
}

export async function searchDocuments(query: string): Promise<SearchResponse> {
  let response: Response;
  try {
    response = await fetch(apiUrl('/api/v1/search'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 5 })
    });
  } catch {
    throw new Error('Suchdienst nicht erreichbar. Bitte prüfe, ob der LumOS Core läuft.');
  }
  if (response.status === 404 || response.status === 405) {
    throw new Error('Suchdienst nicht erreichbar. Der API-Endpunkt ist nicht verfügbar.');
  }
  if (!response.ok) throw await responseError(response, `Suche fehlgeschlagen: ${response.status}`);
  return response.json() as Promise<SearchResponse>;
}

export async function fetchLlmStatus(): Promise<LlmStatusResponse> {
  let response: Response;
  try {
    response = await fetch(apiUrl('/api/v1/llm/status'));
  } catch {
    throw new Error('LLM-Status nicht erreichbar. Der LumOS Core läuft vermutlich nicht.');
  }
  if (!response.ok) throw new Error('LLM-Status konnte nicht geladen werden.');
  return response.json() as Promise<LlmStatusResponse>;
}

export async function generateRagAnswer(query: string): Promise<RagAnswerResponse> {
  let response: Response;
  try {
    response = await fetch(apiUrl('/api/v1/answer'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit: 5 })
    });
  } catch {
    throw new Error('Lokale KI-Antwort nicht erreichbar. Bitte prüfe, ob der LumOS Core läuft.');
  }
  if (response.status === 404 || response.status === 405) {
    throw new Error('Lokale KI-Antwort ist im Backend nicht verfügbar.');
  }
  if (!response.ok) throw await responseError(response, 'Lokale KI-Antwort fehlgeschlagen.');
  return response.json() as Promise<RagAnswerResponse>;
}

export async function checkSearchApi(): Promise<void> {
  const response = await fetch(apiUrl('/api/v1/search'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: '__lumos_search_probe__', limit: 1 })
  });
  if (!response.ok) throw new Error(`Suchdienst nicht bereit: ${response.status}`);
}

export type LetterExportRequest = {
  sender_name?: string;
  sender_address?: string;
  recipient_name?: string;
  recipient_company?: string | null;
  recipient_address?: string;
  date?: string | null;
  subject?: string;
  reference?: string | null;
  salutation?: string;
  body_text?: string;
  closing?: string;
  signoff_name?: string;
  export_formats?: string[];
  custom_filename?: string | null;
  human_approved?: boolean;
};

export type LetterPreviewResponse = {
  formatted_preview_html: string;
  sender: string;
  recipient: string;
  subject: string;
  date: string;
  body_paragraphs: string[];
  word_count: number;
  character_count: number;
};

export type LetterGenerateResponse = {
  success: boolean;
  docx_path: string | null;
  pdf_path: string | null;
  export_dir: string;
  filename_base: string;
  human_approved: boolean;
  created_at: string;
};

export async function previewLetterExport(payload: LetterExportRequest): Promise<LetterPreviewResponse> {
  const response = await fetch(apiUrl('/api/v1/export/letter/preview'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw await responseError(response, 'Brief-Vorschau konnte nicht erzeugt werden.');
  return response.json() as Promise<LetterPreviewResponse>;
}

export async function generateLetterExport(payload: LetterExportRequest): Promise<LetterGenerateResponse> {
  const response = await fetch(apiUrl('/api/v1/export/letter/generate'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, human_approved: true })
  });
  if (!response.ok) throw await responseError(response, 'Geschäftsbrief-Export fehlgeschlagen.');
  return response.json() as Promise<LetterGenerateResponse>;
}

export type HardwareInfoResponse = {
  os_name: string;
  os_version: string;
  cpu_cores_logical: number;
  memory_total_gb: number;
  memory_available_gb: number;
  gpu_name: string | null;
  gpu_acceleration: string;
  recommended_profile: string;
  status: string;
};

export type ModelItem = {
  name: string;
  filename: string;
  path: string;
  size_mb: number;
  allowlist_status: string;
};

export type ModelScanResponse = {
  models_dir: string;
  installed_models: ModelItem[];
  count: number;
};

export type SbomComponent = {
  name: string;
  version: string;
  license: string;
  purpose: string;
  status: string;
};

export type SbomResponse = {
  app_name: string;
  version: string;
  updated_at: string;
  components: SbomComponent[];
};

export async function fetchHardwareInfo(): Promise<HardwareInfoResponse> {
  const response = await fetch(apiUrl('/api/v1/system/hardware'));
  if (!response.ok) throw new Error('Hardware-Informationen konnten nicht geladen werden.');
  return response.json() as Promise<HardwareInfoResponse>;
}

export async function fetchModelScan(): Promise<ModelScanResponse> {
  const response = await fetch(apiUrl('/api/v1/system/models'));
  if (!response.ok) throw new Error('Modell-Verzeichnis konnte nicht gescannt werden.');
  return response.json() as Promise<ModelScanResponse>;
}

export async function fetchSbom(): Promise<SbomResponse> {
  const response = await fetch(apiUrl('/api/v1/system/sbom'));
  if (!response.ok) throw new Error('SBOM konnte nicht abgerufen werden.');
  return response.json() as Promise<SbomResponse>;
}
