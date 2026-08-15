<script lang="ts">
  import { onMount } from 'svelte';
  import { analyzeTable, checkSearchApi, deleteDocument, fetchDocument, fetchDocuments, fetchHardwareInfo, fetchHealth, fetchLlmStatus, fetchMediaList, fetchModelScan, fetchSbom, generateLetterExport, generateLocalImage, generateLocalTts, generateRagAnswer, inspectTable, previewLetterExport, reprocessDocument, searchDocuments, uploadDocument, type DocumentItem, type HardwareInfoResponse, type HealthResponse, type ImageGenerateResponse, type LetterExportRequest, type LetterGenerateResponse, type LetterPreviewResponse, type LlmStatusResponse, type MediaListResponse, type ModelScanResponse, type RagAnswerResponse, type SbomResponse, type SearchResponse, type TableAnalyzeResponse, type TableInspectResponse, type TtsGenerateResponse } from './lib/api';
  let health: HealthResponse | null = null;
  let llmStatus: LlmStatusResponse | null = null;
  let hardwareInfo: HardwareInfoResponse | null = null;
  let modelScan: ModelScanResponse | null = null;
  let sbomInfo: SbomResponse | null = null;
  let showSbomModal = false;
  let searchApiAvailable = false;
  let checking = true;
  let query = '';
  let activeItem = 'Start';
  let documents: DocumentItem[] = [];
  let importing = false;
  let deletingId: string | null = null;
  let processingId: string | null = null;
  let selectedDocument: DocumentItem | null = null;
  let searching = false;
  let searchResult: SearchResponse | null = null;
  let answerResult: RagAnswerResponse | null = null;
  let chatMode: 'search' | 'answer' = 'search';
  let importMessage = 'PDF, DOCX, TXT, Markdown und Bilder bis 25 MB';
  let message = 'Importiere ein Dokument und stelle anschließend eine Frage an deinen lokalen Wissensraum.';
  let lastError = '';
  let showExportModal = false;
  let exportApproved = false;
  let exportingLetter = false;
  let exportResult: LetterGenerateResponse | null = null;
  let previewResult: LetterPreviewResponse | null = null;

  let mediaPrompt = 'Modernes Firmenlogo und Grafik für Geschäftsbrief';
  let ttsText = 'Willkommen bei LumOS Lokal Office. Deine Daten bleiben lokal auf deinem PC.';
  let generatingImage = false;
  let generatingTts = false;
  let imageResult: ImageGenerateResponse | null = null;
  let ttsResult: TtsGenerateResponse | null = null;
  let mediaList: MediaListResponse | null = null;

  let csvInput = "Produkt,Menge,Preis\nBürostuhl,5,149.00\nArbeitstisch,2,399.00\nMonitor,4,220.00\nTastatur,10,29.90";
  let inspectingTable = false;
  let analyzingTable = false;
  let tableInspectResult: TableInspectResponse | null = null;
  let tableAnalyzeResult: TableAnalyzeResponse | null = null;
  let selectedOperation = 'sum';
  let selectedTargetCol = 'Preis';

  async function handleInspectTable() {
    if (!csvInput.trim() || inspectingTable) return;
    inspectingTable = true;
    try {
      tableInspectResult = await inspectTable({ csv_content: csvInput });
      if (tableInspectResult.headers.length > 0 && !selectedTargetCol) {
        selectedTargetCol = tableInspectResult.headers[tableInspectResult.headers.length - 1];
      }
    } catch (err) {
      lastError = err instanceof Error ? err.message : 'Tabellen-Inspektion fehlgeschlagen.';
    } finally {
      inspectingTable = false;
    }
  }

  async function handleAnalyzeTable() {
    if (!csvInput.trim() || analyzingTable) return;
    analyzingTable = true;
    try {
      tableAnalyzeResult = await analyzeTable({
        csv_content: csvInput,
        target_column: selectedTargetCol,
        operation: selectedOperation
      });
    } catch (err) {
      lastError = err instanceof Error ? err.message : 'Kalkulation fehlgeschlagen.';
    } finally {
      analyzingTable = false;
    }
  }

  async function handleGenerateImage() {
    if (!mediaPrompt.trim() || generatingImage) return;
    generatingImage = true;
    try {
      imageResult = await generateLocalImage({ prompt: mediaPrompt });
      await loadMediaList();
    } catch (err) {
      lastError = err instanceof Error ? err.message : 'Bildgenerierung fehlgeschlagen.';
    } finally {
      generatingImage = false;
    }
  }

  async function handleGenerateTts(textToSpeak?: string) {
    const text = textToSpeak || ttsText;
    if (!text.trim() || generatingTts) return;
    generatingTts = true;
    try {
      ttsResult = await generateLocalTts({ text });
      await loadMediaList();
    } catch (err) {
      lastError = err instanceof Error ? err.message : 'Sprachsynthese fehlgeschlagen.';
    } finally {
      generatingTts = false;
    }
  }

  async function loadMediaList() {
    try {
      mediaList = await fetchMediaList();
    } catch {
      mediaList = null;
    }
  }

  let exportForm: LetterExportRequest = {
    sender_name: 'Studio M 360 GmbH',
    sender_address: 'Musterstraße 12, 10115 Berlin',
    recipient_name: 'Max Mustermann',
    recipient_company: 'Musterfirma AG',
    recipient_address: 'Hauptstraße 45, 80331 München',
    subject: 'Ihr Angebot und Informationen zum Projekt',
    reference: 'Ref-Nr. LumOS-2026-0815',
    salutation: 'Sehr geehrte Damen und Herren,',
    body_text: 'vielen Dank für Ihre Anfrage. Anbei erhalten Sie die gewünschten Informationen.',
    closing: 'Mit freundlichen Grüßen',
    signoff_name: 'Ihr LumOS Team',
    custom_filename: 'geschaeftsbrief_angebot'
  };

  async function updatePreview() {
    try {
      previewResult = await previewLetterExport(exportForm);
    } catch {
      previewResult = null;
    }
  }

  async function openExportModal(text?: string) {
    if (text) {
      exportForm.body_text = text;
    }
    showExportModal = true;
    exportApproved = false;
    exportResult = null;
    await updatePreview();
  }

  async function executeExport() {
    if (!exportApproved || exportingLetter) return;
    exportingLetter = true;
    try {
      exportResult = await generateLetterExport(exportForm);
    } catch (error) {
      lastError = error instanceof Error ? error.message : 'Export fehlgeschlagen.';
    } finally {
      exportingLetter = false;
    }
  }
  const formatNumber = (value: unknown) => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric.toLocaleString('de-DE') : '0';
  };
  $: readyDocuments = documents.filter((document) => document.status === 'ready').length;
  $: failedDocuments = documents.filter((document) => document.status === 'failed' || document.status === 'unsupported').length;
  $: latestDocumentError = documents.find((document) => document.error_message)?.error_message || '';
  $: systemError = lastError || latestDocumentError || 'Keine aktuelle Fehlermeldung.';
  $: coreReady = Boolean(health && searchApiAvailable);
  $: llmReady = Boolean(llmStatus?.generation_available);
  const navItems = ['Start', 'KI-Chat', 'Wissenszentrum', 'Medien & Grafik', 'Dokumente', 'System'];
  async function checkCore() {
    checking = true;
    searchApiAvailable = false;
    try {
      const coreHealth = await fetchHealth();
      await checkSearchApi();
      llmStatus = await fetchLlmStatus();
      hardwareInfo = await fetchHardwareInfo().catch(() => null);
      modelScan = await fetchModelScan().catch(() => null);
      sbomInfo = await fetchSbom().catch(() => null);
      await loadMediaList();
      health = coreHealth;
      searchApiAvailable = true;
      lastError = '';
    } catch (error) {
      health = null;
      llmStatus = null;
      hardwareInfo = null;
      modelScan = null;
      sbomInfo = null;
      mediaList = null;
      searchApiAvailable = false;
      lastError = error instanceof Error ? error.message : 'Backend nicht erreichbar.';
    } finally {
      checking = false;
    }
  }
  async function submitQuery() {
    const value = query.trim();
    if (!value) return;
    searching = true;
    searchResult = null;
    answerResult = null;
    try {
      if (chatMode === 'answer') {
        answerResult = await generateRagAnswer(value);
        if (answerResult.llm_available === false) {
          message = 'Die lokale KI ist aktuell nicht erreichbar. Die gefundenen Quellen bleiben unten sichtbar.';
        } else if (answerResult.insufficient_evidence) {
          message = 'Die vorhandenen Dokumente enthalten dafür keine ausreichenden Informationen.';
        } else {
          message = answerResult.answer;
        }
      } else {
        searchResult = await searchDocuments(value);
        message = searchResult.evidence_found
          ? `${searchResult.count} belegte Fundstelle${searchResult.count === 1 ? '' : 'n'} im lokalen Wissensraum gefunden.`
          : `Für „${value}“ wurde in den fertig verarbeiteten Dokumenten kein belastbarer Beleg gefunden.`;
      }
    } catch (error) {
      message = error instanceof Error ? error.message : 'Die lokale Suche ist fehlgeschlagen.';
      lastError = message;
    } finally {
      searching = false;
    }
  }
  async function loadDocuments() { try { documents = await fetchDocuments(); lastError = ''; } catch (error) { documents = []; importMessage = error instanceof Error ? error.message : 'Dokumentliste konnte nicht geladen werden.'; lastError = importMessage; } }
  async function importFile(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || importing) return;
    importing = true;
    try {
      const result = await uploadDocument(file);
      importMessage = result.duplicate
        ? result.document.status === 'ready' ? 'Dieses Dokument ist bereits gespeichert und durchsuchbar.' : 'Dieses Dokument ist bereits gespeichert, aber noch nicht durchsuchbar.'
        : `${result.document.name}: ${statusLabel(result.document.status)}.`;
      await loadDocuments();
    } catch (error) {
      importMessage = error instanceof Error ? error.message : 'Der Import ist fehlgeschlagen.';
      lastError = importMessage;
    } finally {
      importing = false;
      input.value = '';
    }
  }
  async function removeDocument(item: DocumentItem) {
    if (deletingId || !confirm(`„${item.name}“ wirklich aus dem Wissensraum entfernen?`)) return;
    deletingId = item.id;
    try {
      await deleteDocument(item.id);
      documents = documents.filter((document) => document.id !== item.id);
      searchResult = null;
      importMessage = `${item.name} wurde entfernt.`;
    } catch (error) {
      importMessage = error instanceof Error ? error.message : 'Das Dokument konnte nicht entfernt werden.';
      lastError = importMessage;
    } finally {
      deletingId = null;
    }
  }
  async function openDocument(item: DocumentItem) {
    try { selectedDocument = await fetchDocument(item.id); }
    catch (error) { importMessage = error instanceof Error ? error.message : 'Details konnten nicht geladen werden.'; lastError = importMessage; }
  }
  async function processDocument(item: DocumentItem) {
    if (processingId) return;
    processingId = item.id;
    try {
      const updated = await reprocessDocument(item.id);
      documents = documents.map((document) => document.id === updated.id ? updated : document);
      selectedDocument = selectedDocument?.id === updated.id ? await fetchDocument(updated.id) : selectedDocument;
      importMessage = `${updated.name}: ${updated.status}.`;
    } catch (error) {
      importMessage = error instanceof Error ? error.message : 'Neuverarbeitung fehlgeschlagen.';
      lastError = importMessage;
    } finally { processingId = null; }
  }
  const statusLabel = (status: DocumentItem['status']) => ({ stored: 'Gespeichert – Verarbeitung ausstehend', processing: 'In Verarbeitung', ready: 'Durchsuchbar', failed: 'Fehlgeschlagen', unsupported: 'Nicht unterstützt' })[status];
  function activate(item: string) {
    activeItem = item;
    if (item === 'Dokumente' || item === 'Wissenszentrum') setTimeout(() => document.querySelector('#documents')?.scrollIntoView(), 0);
    if (item === 'KI-Chat') setTimeout(() => document.querySelector('#chat')?.scrollIntoView(), 0);
  }
  onMount(async () => { await checkCore(); await loadDocuments(); });
</script>

<svelte:head><title>LumOS – Lokales KI Office</title></svelte:head>

<div class="app">
  <header>
    <button class="brand" on:click={() => activate('Start')}><img src="/lumos-icon.png" alt="LumOS Symbol"/><span><b>LumOS</b><small>LOKALES KI OFFICE</small></span></button>
    <nav aria-label="Hauptnavigation">{#each navItems as item}<button class:active={activeItem===item} on:click={() => activate(item)}>{item}</button>{/each}</nav>
    <button class="launch" on:click={checkCore}>{coreReady ? 'Core bereit' : checking ? 'Prüfe Core' : 'Core prüfen'} <span>›</span></button>
  </header>

  <main>
    <section class="hero">
      <div class="hero-glow"></div>
      <div class="eyebrow">✦ LOKAL · SICHER · NACHVOLLZIEHBAR</div>
      <h1>Dein Office. Deine Daten.<br/>Deine <strong>lokale KI.</strong></h1>
      <p>LumOS verbindet dein Unternehmenswissen mit einer privaten KI, die lokal auf deinem Windows-PC arbeitet.</p>
      <div class="hero-actions"><button class="launch big" on:click={() => activate('KI-Chat')}>LumOS starten <span>›</span></button><button class="ghost" on:click={() => activate('Wissenszentrum')}>Wissen hinzufügen</button></div>
      <div class="visual">
        <div class="grid-lines"></div><div class="halo"></div>
        <img src="/lumos-logo.png" alt="LumOS Lokal KI Office Logo"/>
        <span class="float-tag tag-a">✓ 100 % lokal</span><span class="float-tag tag-b">◆ Human in Control</span>
      </div>
    </section>

    <section class="control-center" id="system">
      <div>
        <p class="eyebrow">LOKALES CONTROL CENTER</p>
        <h2>Systemstatus.<br/><span>Alles auf einen Blick.</span></h2>
        <p>LumOS prüft Backend, Such-API und Dokumentindex getrennt. Erst fertig verarbeitete Dokumente zählen als RAG-bereit.</p>
      </div>
      <div class="status-grid">
        <article class:online={health}><span>Backend</span><b>{health ? 'Erreichbar' : checking ? 'Prüfung läuft' : 'Nicht erreichbar'}</b><small>{health?.version ? `Version ${health.version}` : 'FastAPI Core auf 127.0.0.1:8765'}</small></article>
        <article class:online={searchApiAvailable}><span>RAG-Suche</span><b>{searchApiAvailable ? 'Verfügbar' : 'Nicht verfügbar'}</b><small>POST /api/v1/search</small></article>
        <article class:online={llmReady} class:error={Boolean(llmStatus?.last_error)}><span>Lokale KI</span><b>{llmReady ? 'Antwortbereit' : llmStatus?.configured ? 'Nicht erreichbar' : 'Nicht konfiguriert'}</b><small>{llmStatus?.model || 'LUMOS_LLM_MODEL nicht gesetzt'} · llama-server optional</small></article>
        <article><span>Dokumente</span><b>{formatNumber(documents.length)}</b><small>lokal gespeichert</small></article>
        <article class:online={readyDocuments > 0}><span>RAG-bereit</span><b>{formatNumber(readyDocuments)}</b><small>{formatNumber(failedDocuments)} mit Fehler oder nicht unterstützt</small></article>
        <article class:error={systemError !== 'Keine aktuelle Fehlermeldung.'}><span>Letzte Meldung</span><b>{systemError}</b><small>{coreReady ? 'Core bereit' : 'Status bitte prüfen'}</small></article>
      </div>
    </section>

    <section class="promise">
      <p class="eyebrow">DAS IST LUMOS</p>
      <h2>Ein lokales KI-Arbeitszentrum.<br/><span>Für dein echtes Büro.</span></h2>
      <div class="cards">
        <article><b>01</b><i>⌁</i><h3>Lokaler KI-Chat</h3><p>Fragen stellen und belegte Antworten aus freigegebenen Dokumenten erhalten.</p></article>
        <article><b>02</b><i>◇</i><h3>Wissenszentrum</h3><p>Unternehmenswissen sicher erfassen, ordnen und intelligent durchsuchen.</p></article>
        <article><b>03</b><i>↗</i><h3>Office-Ergebnisse</h3><p>Geschäftsdokumente kontrolliert vorbereiten, prüfen und exportieren.</p></article>
      </div>
    </section>

    <section class="document-center" id="documents">
      <div class="document-intro">
        <p class="eyebrow">LOKALES WISSENSZENTRUM</p>
        <h2>Deine Dokumente.<br/><span>Sicher auf deinem PC.</span></h2>
        <p>Beim Import prüft LumOS Dateityp, Größe und Inhalt, erzeugt eine eindeutige SHA-256-Identität und verändert das Original nicht.</p>
        <label class:busy={importing} class="upload-button">
          <input type="file" accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg" on:change={importFile} disabled={importing}/>
          {importing ? 'Dokument wird geprüft …' : 'Dokument hinzufügen'} <span>＋</span>
        </label>
        <small class="import-message">{importMessage}</small>
      </div>
      <div class="document-panel">
        <div class="panel-head"><span>FREIGEGEBENER WISSENSRAUM</span><b>{documents.length} DOKUMENT{documents.length===1?'':'E'}</b></div>
        {#if documents.length === 0}
          <div class="empty-state"><i>◇</i><h3>Noch kein Dokument</h3><p>Füge dein erstes freigegebenes Dokument hinzu. Alle Daten bleiben lokal.</p></div>
        {:else}
          <div class="document-list">{#each documents as item}<article><b>{item.type}</b><div><h3>{item.name}</h3><p>{(Number(item.size) || 0)/1024 < 0.1 ? '0,0' : ((Number(item.size) || 0)/1024).toFixed(1)} KB · {formatNumber(item.character_count ?? item.extracted_chars)} Zeichen · {formatNumber(item.chunk_count)} Chunks · {item.sha256?.slice(0,12) || '–'}…</p>{#if item.status !== 'ready' && (Number(item.character_count ?? item.extracted_chars) || 0) === 0}<small class="document-warning">Noch nicht RAG-bereit: bitte neu verarbeiten oder Fehler prüfen.</small>{/if}{#if item.error_message}<small class="document-error">{item.error_message}</small>{/if}</div><div class="document-actions"><span class:failed={item.status === 'failed' || item.status === 'unsupported'}>{statusLabel(item.status)}</span><div><button type="button" on:click={() => openDocument(item)}>Details / Öffnen</button><button type="button" on:click={() => processDocument(item)} disabled={processingId === item.id}>{processingId === item.id ? 'Verarbeite …' : 'Neu verarbeiten'}</button><button class="danger" type="button" on:click={() => removeDocument(item)} disabled={deletingId === item.id}>{deletingId === item.id ? 'Entferne …' : 'Löschen'}</button></div></div></article>{/each}</div>
        {/if}
      </div>
    </section>

    {#if selectedDocument}
      <div class="document-modal">
        <div class="document-modal-card" role="dialog" aria-modal="true" aria-label="Dokumentdetails" tabindex="-1">
          <button class="modal-close" aria-label="Schließen" on:click={() => selectedDocument = null}>×</button>
          <p class="eyebrow">DOKUMENTDETAILS</p><h2>{selectedDocument.name}</h2>
          <dl><div><dt>Status</dt><dd>{statusLabel(selectedDocument.status)}</dd></div><div><dt>Größe</dt><dd>{((Number(selectedDocument.size) || 0)/1024).toFixed(1)} KB</dd></div><div><dt>Zeichen</dt><dd>{formatNumber(selectedDocument.character_count ?? selectedDocument.extracted_chars)}</dd></div><div><dt>Chunks</dt><dd>{formatNumber(selectedDocument.chunk_count)}</dd></div><div><dt>SHA-256</dt><dd>{selectedDocument.sha256}</dd></div></dl>
          {#if selectedDocument.error_message}<p class="document-error">{selectedDocument.error_message}</p>{/if}
          <h3>Extrahierter Text</h3><pre>{selectedDocument.content || 'Kein extrahierter Text verfügbar.'}</pre>
        </div>
      </div>
    {/if}

    {#if showExportModal}
      <div class="document-modal">
        <div class="export-modal-card" role="dialog" aria-modal="true" aria-label="Geschäftsbrief Export" tabindex="-1">
          <button class="modal-close" aria-label="Schließen" on:click={() => showExportModal = false}>×</button>
          <p class="eyebrow">ACTION PREVIEW & HUMAN APPROVAL</p>
          <h2>Geschäftsbrief erzeugen</h2>
          <p>Prüfe und bearbeite die Pflichtfelder vor der Freigabe. LumOS erzeugt daraus saubere DOCX- und PDF-Dateien.</p>

          <div class="export-grid">
            <div class="export-form">
              <label>Absender Name <input bind:value={exportForm.sender_name} on:input={updatePreview}/></label>
              <label>Absender Adresse <input bind:value={exportForm.sender_address} on:input={updatePreview}/></label>
              <label>Empfänger Name <input bind:value={exportForm.recipient_name} on:input={updatePreview}/></label>
              <label>Empfänger Firma <input bind:value={exportForm.recipient_company} on:input={updatePreview}/></label>
              <label>Empfänger Adresse <input bind:value={exportForm.recipient_address} on:input={updatePreview}/></label>
              <label>Betreff <input bind:value={exportForm.subject} on:input={updatePreview}/></label>
              <label>Bezugszeichen <input bind:value={exportForm.reference} on:input={updatePreview}/></label>
              <label>Anrede <input bind:value={exportForm.salutation} on:input={updatePreview}/></label>
              <label>Brieftext <textarea bind:value={exportForm.body_text} on:input={updatePreview}></textarea></label>
              <label>Grußformel <input bind:value={exportForm.closing} on:input={updatePreview}/></label>
              <label>Unterzeichner <input bind:value={exportForm.signoff_name} on:input={updatePreview}/></label>
              <label>Dateiname <input bind:value={exportForm.custom_filename}/></label>
            </div>

            <div class="preview-panel">
              <p class="eyebrow">VISUELLE VORSCHAU (DIN 5008)</p>
              {#if previewResult}
                <div class="letter-preview-box">
                  {@html previewResult.formatted_preview_html}
                </div>
                <small style="color: #9ec9e9; display: block; margin-top: 10px;">
                  Umfang: {previewResult.word_count} Wörter · {previewResult.character_count} Zeichen
                </small>
              {:else}
                <p>Vorschau wird geladen …</p>
              {/if}
            </div>
          </div>

          <div class="approval-box">
            <label>
              <input type="checkbox" bind:checked={exportApproved}/>
              <b>Ich habe den Geschäftsbrief geprüft und gebe die Erzeugung als DOCX & PDF im lokalen Export-Ordner frei (Human in Control).</b>
            </label>
          </div>

          {#if exportResult}
            <div style="margin-top: 15px; padding: 15px; background: #0c3311; border: 1px solid #8cff0066; border-radius: 12px; color: #d8ffab;">
              <b>✓ Geschäftsbrief erfolgreich freigegeben & gespeichert!</b>
              {#if exportResult.docx_path}<p style="margin: 5px 0 0; font-size: 0.8rem;">DOCX: {exportResult.docx_path}</p>{/if}
              {#if exportResult.pdf_path}<p style="margin: 3px 0 0; font-size: 0.8rem;">PDF: {exportResult.pdf_path}</p>{/if}
            </div>
          {/if}

          <div class="export-actions">
            <button type="button" class="ghost" on:click={() => showExportModal = false}>Abbrechen</button>
            <button type="button" class="confirm" disabled={!exportApproved || exportingLetter} on:click={executeExport}>
              {exportingLetter ? 'Erzeuge Dateien …' : 'Freigeben & DOCX + PDF speichern'}
            </button>
          </div>
        </div>
      </div>
    {/if}

    <section class="workspace" id="chat">
      <div class="workspace-copy"><p class="eyebrow">BELEGTE LOKALE SUCHE</p><h2>Frag dein<br/><span>Wissen.</span></h2><p>LumOS durchsucht ausschließlich deine freigegebenen lokalen Dokumente und zeigt jede verwendete Fundstelle offen an.</p></div>
      <div class="chat-card">
        <div class="chat-head"><span>LUMOS / KI-CHAT</span><span class="state"><i class:online={coreReady}></i>{coreReady?'CORE BEREIT':'CORE OFFLINE'} · {llmReady ? llmStatus?.model : 'LLM optional'}</span></div>
        <form on:submit|preventDefault={submitQuery}>
          <div class="chat-mode" aria-label="Chat-Modus">
            <button type="button" class:active={chatMode === 'search'} on:click={() => chatMode = 'search'}>Quellen suchen</button>
            <button type="button" class:active={chatMode === 'answer'} on:click={() => chatMode = 'answer'}>Lokale KI-Antwort</button>
          </div>
          <textarea bind:value={query} placeholder={chatMode === 'answer' ? 'Welche quellengebundene Antwort soll LumOS lokal erzeugen?' : 'Was möchtest du in deinen Dokumenten finden?'}></textarea>
          <button type="submit" disabled={searching}>{searching ? chatMode === 'answer' ? 'Antwort entsteht …' : 'Suche läuft …' : chatMode === 'answer' ? 'Lokal beantworten' : 'Lokal suchen'} <span>›</span></button>
        </form>
        {#if answerResult}
          {#if answerResult.llm_available === false || answerResult.warning}
            <div class="llm-warning-card">
              <b>⚠️ Lokale KI nicht erreichbar</b>
              <p>{answerResult.warning || 'Die Quellen wurden gefunden, aber es konnte keine KI-Antwort erzeugt werden.'}</p>
              <small>Hinweis: Bitte starte <code>start-llm.ps1</code> in der PowerShell, um das Sprachmodell (llama-server) bereitzustellen.</small>
            </div>
          {:else if answerResult.insufficient_evidence}
            <div class="llm-info-card">
              <b>ℹ️ Keine ausreichende Evidenz</b>
              <p>Die vorhandenen Dokumente enthalten dafür keine ausreichenden Informationen.</p>
            </div>
          {:else if answerResult.answer}
            <div class="answer-box">
              <div class="answer-head">
                <span>LOKALE KI-ANTWORT</span>
                {#if answerResult.model}<small>Modell: {answerResult.model}</small>{/if}
              </div>
              <p>{answerResult.answer}</p>
              <button type="button" class="export-button" on:click={() => openExportModal(answerResult?.answer)}>✉️ Als Geschäftsbrief exportieren (DOCX + PDF)</button>
              <button type="button" class="export-button" style="margin-left: 8px;" on:click={() => handleGenerateTts(answerResult?.answer)} disabled={generatingTts}>{generatingTts ? 'Erzeuge Audio …' : '🔊 Vorlesen (TTS)'}</button>
            </div>
          {/if}
          {#if answerResult.sources && answerResult.sources.length > 0}
            <div class="sources">
              <div class="sources-head">GEFUNDENE QUELLEN / {answerResult.sources.length} FUNDSTELLEN</div>
              {#each answerResult.sources as hit, index}
                <article>
                  <b>[{index+1}]</b>
                  <div>
                    <h3>{hit.document_name} <small>{hit.page ? `· Seite ${hit.page}` : `· ${hit.section}`}</small></h3>
                    <p>{hit.excerpt.length > 280 ? hit.excerpt.slice(0, 280) + '...' : hit.excerpt}</p>
                    <span class="score-badge">Trefferwert {hit.score.toFixed(2)}</span>
                  </div>
                </article>
              {/each}
            </div>
          {/if}
        {/if}
        {#if searchResult}
          {#if searchResult.evidence_found}
            <div class="sources">
              <div class="sources-head">GEFUNDENE QUELLEN / {searchResult.count} FUNDSTELLEN</div>
              {#each searchResult.hits as hit, index}
                <article>
                  <b>[{index+1}]</b>
                  <div>
                    <h3>{hit.document_name} <small>{hit.page ? `· Seite ${hit.page}` : `· ${hit.section}`}</small></h3>
                    <p>{hit.excerpt.length > 280 ? hit.excerpt.slice(0, 280) + '...' : hit.excerpt}</p>
                    <span class="score-badge">Trefferwert {hit.score.toFixed(2)}</span>
                  </div>
                </article>
              {/each}
            </div>
          {:else}
            <div class="llm-info-card">
              <b>Keine Fundstellen</b>
              <p>Keine passende Fundstelle in fertig verarbeiteten Dokumenten gefunden.</p>
            </div>
          {/if}
        {/if}
      </div>
    </section>

    <section class="document-center" id="media">
      <div class="document-intro">
        <p class="eyebrow">LOKALE MEDIENGENERATION (GATE 6)</p>
        <h2>Bilder & Sprache.<br/><span>Rechtssicher auf deinem PC.</span></h2>
        <p>Erzeuge Produktbilder, Illustrationen und Sprachsynthese (TTS) lokal ohne Cloud-Dienste – 100 % kommerziell frei nutzbar (Apache-2.0 / MIT).</p>

        <div style="margin-top: 15px; display: flex; flex-direction: column; gap: 10px;">
          <label style="font-size: 0.76rem; color: #9ec9e9; display: flex; flex-direction: column; gap: 4px;">
            Bild-Beschreibung (Prompt)
            <input type="text" bind:value={mediaPrompt} style="background: #020a18; border: 1px solid #4098d744; border-radius: 8px; color: white; padding: 8px 12px; font: inherit; font-size: 0.82rem;"/>
          </label>
          <button type="button" class="export-button" on:click={handleGenerateImage} disabled={generatingImage}>
            {generatingImage ? 'Generiere Bild …' : '🖼️ Bild erzeugen (Apache-2.0)'}
          </button>

          {#if imageResult}
            <div style="margin-top: 10px; padding: 12px; background: #041b38; border: 1px solid #4098d744; border-radius: 12px;">
              <b style="color: #70d8ff; font-size: 0.82rem;">✓ Bild erzeugt: {imageResult.filename}</b>
              <p style="margin: 4px 0; font-size: 0.75rem; color: #9ec9e9;">Provider: {imageResult.provider} ({imageResult.width}x{imageResult.height})</p>
              <small style="color: #8cff00; font-size: 0.72rem;">Lizenz: {imageResult.license_status}</small>
            </div>
          {/if}

          <label style="margin-top: 10px; font-size: 0.76rem; color: #9ec9e9; display: flex; flex-direction: column; gap: 4px;">
            Sprachsynthese Text (TTS)
            <textarea bind:value={ttsText} style="background: #020a18; border: 1px solid #4098d744; border-radius: 8px; color: white; padding: 8px 12px; font: inherit; font-size: 0.82rem; min-height: 70px;"></textarea>
          </label>
          <button type="button" class="export-button" on:click={() => handleGenerateTts()} disabled={generatingTts}>
            {generatingTts ? 'Erzeuge Audio …' : '🔊 Vorlese-Audio erzeugen (Piper TTS)'}
          </button>

          {#if ttsResult}
            <div style="margin-top: 10px; padding: 12px; background: #041b38; border: 1px solid #4098d744; border-radius: 12px;">
              <b style="color: #70d8ff; font-size: 0.82rem;">✓ Audio erzeugt: {ttsResult.filename}</b>
              <p style="margin: 4px 0; font-size: 0.75rem; color: #9ec9e9;">Dauer: {ttsResult.duration_seconds} Sekunden · Stimmsynthese: {ttsResult.voice}</p>
            </div>
          {/if}
        </div>
      </div>

      <div class="document-panel">
        <div class="panel-head">
          <span>GENERIERTE MEDIEN (`core/data/media/`)</span>
          <b>{mediaList?.count || 0} DATEI(EN)</b>
        </div>
        {#if !mediaList || mediaList.items.length === 0}
          <div class="empty-state">
            <i>◇</i>
            <h3>Noch keine Medien generiert</h3>
            <p>Erstelle dein erstes lokales Bild oder eine Vorlese-Audiodatei.</p>
          </div>
        {:else}
          <div class="document-list">
            {#each mediaList.items as item}
              <article>
                <b>{item.type.toUpperCase()}</b>
                <div>
                  <h3>{item.filename}</h3>
                  <p>{(item.size_bytes / 1024).toFixed(1)} KB · {item.path}</p>
                </div>
              </article>
            {/each}
          </div>
        {/if}
      </div>
    </section>

    <section class="document-center" id="tables">
      <div class="document-intro">
        <p class="eyebrow">TABELLEN & FINANZ-ANALYSE (GATE 7)</p>
        <h2>Zahlen & Kalkulationen.<br/><span>Präzise auf deinem PC.</span></h2>
        <p>Analysiere CSV- und Tabellendaten, berechne Summen, Mittelwerte und erstelle strukturierte Übersichten für Angebote und Berichte.</p>

        <div style="margin-top: 15px; display: flex; flex-direction: column; gap: 10px;">
          <label style="font-size: 0.76rem; color: #9ec9e9; display: flex; flex-direction: column; gap: 4px;">
            Tabellendaten (CSV / Semikolon / Komma)
            <textarea bind:value={csvInput} style="background: #020a18; border: 1px solid #4098d744; border-radius: 8px; color: white; padding: 8px 12px; font: inherit; font-size: 0.82rem; min-height: 100px;"></textarea>
          </label>
          <div style="display: flex; gap: 10px;">
            <button type="button" class="export-button" on:click={handleInspectTable} disabled={inspectingTable}>
              {inspectingTable ? 'Analysiere …' : '📊 Tabelle analysieren'}
            </button>
            <button type="button" class="export-button" on:click={handleAnalyzeTable} disabled={analyzingTable}>
              {analyzingTable ? 'Rechne …' : '🧮 Kalkulation durchführen'}
            </button>
          </div>

          <div style="display: flex; gap: 10px; margin-top: 5px;">
            <label style="font-size: 0.75rem; color: #9ec9e9; flex: 1;">
              Ziel-Spalte:
              <input type="text" bind:value={selectedTargetCol} style="width: 100%; background: #020a18; border: 1px solid #4098d744; border-radius: 6px; color: white; padding: 4px 8px; margin-top: 2px;"/>
            </label>
            <label style="font-size: 0.75rem; color: #9ec9e9; flex: 1;">
              Operation:
              <select bind:value={selectedOperation} style="width: 100%; background: #020a18; border: 1px solid #4098d744; border-radius: 6px; color: white; padding: 4px 8px; margin-top: 2px;">
                <option value="sum">Summe (SUM)</option>
                <option value="avg">Durchschnitt (AVG)</option>
                <option value="min">Minimum (MIN)</option>
                <option value="max">Maximum (MAX)</option>
                <option value="count">Anzahl (COUNT)</option>
              </select>
            </label>
          </div>

          {#if tableAnalyzeResult}
            <div style="margin-top: 10px; padding: 14px; background: #052445; border: 1px solid #70d8ff88; border-radius: 12px; color: white;">
              {@html tableAnalyzeResult.summary_html}
            </div>
          {/if}
        </div>
      </div>

      <div class="document-panel">
        <div class="panel-head">
          <span>TABELLEN-VORSCHAU & SPALTEN</span>
          <b>{tableInspectResult?.row_count || 0} ZEILEN</b>
        </div>
        {#if !tableInspectResult}
          <div class="empty-state">
            <i>◇</i>
            <h3>Klicke "Tabelle analysieren"</h3>
            <p>LumOS ermittelt Spalten, Datentypen, Min/Max und Summen-Statistiken.</p>
          </div>
        {:else}
          <div style="padding: 15px; overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem; text-align: left;">
              <thead>
                <tr style="border-bottom: 1px solid #4098d766; color: #70d8ff;">
                  {#each tableInspectResult.headers as header}
                    <th style="padding: 6px 10px;">{header}</th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each tableInspectResult.preview_rows as row}
                  <tr style="border-bottom: 1px solid #4098d722;">
                    {#each row as cell}
                      <td style="padding: 6px 10px; color: #e1eeff;">{cell}</td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </section>

    <section class="document-center" id="system">
      <div class="document-intro">
        <p class="eyebrow">SYSTEM & HARDWARE-ASSISTENT</p>
        <h2>Lokale Leistung.<br/><span>Transparent geprüft.</span></h2>
        <p>LumOS analysiert deine Hardware und Modelle auf Konformität mit der Sicherheits-Allowlist (ADR-009 / Security Policy).</p>

        {#if hardwareInfo}
          <div style="margin-top: 15px; padding: 16px; background: #041b38; border: 1px solid #4098d744; border-radius: 14px; font-size: 0.82rem;">
            <b>🖥️ System: {hardwareInfo.os_name}</b>
            <p style="margin: 4px 0 0; color: #9ec9e9;">RAM: {hardwareInfo.memory_total_gb} GB Gesamt ({hardwareInfo.memory_available_gb} GB frei)</p>
            <p style="margin: 2px 0 0; color: #9ec9e9;">CPU: {hardwareInfo.cpu_cores_logical} logische Kerne</p>
            <p style="margin: 2px 0 0; color: #7ed6ff;">GPU: {hardwareInfo.gpu_name || 'Standard-Grafikeinheit'}</p>
            <p style="margin: 2px 0 0; color: #8cff00;">Beschleunigung: {hardwareInfo.gpu_acceleration}</p>
            <small style="display: block; margin-top: 8px; color: #c0e4ff;">Empfohlenes Modellprofil: {hardwareInfo.recommended_profile}</small>
          </div>
        {/if}

        <button type="button" class="export-button" style="margin-top: 15px;" on:click={() => showSbomModal = true}>
          📄 SBOM & Lizenz-Inventar anzeigen
        </button>
      </div>

      <div class="document-panel">
        <div class="panel-head">
          <span>MODELL-ALLOWLIST & VERZEICHNIS (`models/`)</span>
          <b>{modelScan?.count || 0} MODELL(E)</b>
        </div>
        {#if !modelScan || modelScan.installed_models.length === 0}
          <div class="empty-state">
            <i>◇</i>
            <h3>Keine GGUF-Dateien in `models/`</h3>
            <p>Lege ein geprüftes GGUF-Modell (z. B. `Qwen2.5-7B-Instruct-GGUF`) im Unterordner `models/` ab.</p>
          </div>
        {:else}
          <div class="document-list">
            {#each modelScan.installed_models as model}
              <article>
                <b>GGUF</b>
                <div>
                  <h3>{model.name}</h3>
                  <p>{model.size_mb} MB · {model.path}</p>
                  <small style="color: {model.allowlist_status === 'candidate' ? '#ffe066' : model.allowlist_status === 'approved' ? '#8cff00' : '#ff765c'}">
                    Status Allowlist: <b>{model.allowlist_status.toUpperCase()}</b>
                  </small>
                </div>
              </article>
            {/each}
          </div>
        {/if}
      </div>
    </section>

    {#if showSbomModal && sbomInfo}
      <div class="document-modal">
        <div class="export-modal-card" role="dialog" aria-modal="true" aria-label="Software Bill of Materials" tabindex="-1">
          <button class="modal-close" aria-label="Schließen" on:click={() => showSbomModal = false}>×</button>
          <p class="eyebrow">SOFTWARE BILL OF MATERIALS (ADR-009 / LIZENZINVENTAR)</p>
          <h2>{sbomInfo.app_name} v{sbomInfo.version} - SBOM</h2>
          <p style="color: #9ec9e9;">Stand: {sbomInfo.updated_at} · Maschinenlesbar gespeichert unter `docs/licenses/sbom.json`</p>

          <div style="margin-top: 20px; overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem; text-align: left;">
              <thead>
                <tr style="border-bottom: 1px solid #4098d766; color: #70d8ff;">
                  <th style="padding: 8px;">Komponente</th>
                  <th style="padding: 8px;">Version</th>
                  <th style="padding: 8px;">Lizenz</th>
                  <th style="padding: 8px;">Zweck</th>
                  <th style="padding: 8px;">Status</th>
                </tr>
              </thead>
              <tbody>
                {#each sbomInfo.components as comp}
                  <tr style="border-bottom: 1px solid #4098d722;">
                    <td style="padding: 8px; font-weight: bold;">{comp.name}</td>
                    <td style="padding: 8px; color: #c0e4ff;">{comp.version}</td>
                    <td style="padding: 8px; color: #8bdcff;">{comp.license}</td>
                    <td style="padding: 8px; color: #9ec9e9;">{comp.purpose}</td>
                    <td style="padding: 8px;">
                      <span style="padding: 2px 6px; border-radius: 4px; background: {comp.status === 'approved' ? '#0d3810' : comp.status === 'candidate' ? '#3d3408' : '#3d141e'}; color: {comp.status === 'approved' ? '#8cff00' : comp.status === 'candidate' ? '#ffe066' : '#ff765c'}; font-size: 0.72rem; font-weight: bold;">
                        {comp.status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <div class="export-actions">
            <button type="button" class="confirm" on:click={() => showSbomModal = false}>Schließen</button>
          </div>
        </div>
      </div>
    {/if}

    <section class="status-section">
      <p class="eyebrow">ENTWICKLUNGSSTATUS</p><h2>Die Basis steht.<br/><span>Jetzt wird LumOS intelligent.</span></h2>
      <div class="steps"><div class="done"><b>01</b><span>Oberfläche</span><small>BEREIT</small></div><div class:done={coreReady}><b>02</b><span>Lokaler Core</span><small>{coreReady?'BEREIT':'PRÜFEN'}</small></div><div class:done={documents.length > 0}><b>03</b><span>Dokumentaufnahme</span><small>{documents.length > 0 ? 'AKTIV' : 'LEER'}</small></div><div class:done={readyDocuments > 0}><b>04</b><span>Textextraktion & Suche</span><small>{readyDocuments > 0 ? 'BEREIT' : 'WARTET'}</small></div><div class:done={coreReady && readyDocuments > 0}><b>05</b><span>Lokales KI-Modell & Export</span><small>{readyDocuments > 0 ? 'BEREIT' : 'ALS NÄCHSTES'}</small></div></div>
    </section>
  </main>
  <footer><div><b>LumOS</b><small>LOKAL KI OFFICE</small></div><span>Studio M 360 · Development & Consulting</span><span>LOCAL FIRST · OFFLINE FIRST</span></footer>
</div>
