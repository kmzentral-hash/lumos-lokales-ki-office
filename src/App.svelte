<script lang="ts">
  import { onMount } from 'svelte';
  import { checkSearchApi, deleteDocument, fetchDocument, fetchDocuments, fetchHealth, reprocessDocument, searchDocuments, uploadDocument, type DocumentItem, type HealthResponse, type SearchResponse } from './lib/api';
  let health: HealthResponse | null = null;
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
  let importMessage = 'PDF, DOCX, TXT, Markdown und Bilder bis 25 MB';
  let message = 'Importiere ein Dokument und stelle anschließend eine Frage an deinen lokalen Wissensraum.';
  const navItems = ['Start', 'KI-Chat', 'Wissenszentrum', 'Dokumente', 'System'];
  async function checkCore() { checking = true; try { const coreHealth = await fetchHealth(); await checkSearchApi(); health = coreHealth; } catch { health = null; } finally { checking = false; } }
  async function submitQuery() {
    const value=query.trim(); if(!value)return;
    searching = true; searchResult = null;
    try {
      searchResult = await searchDocuments(value);
      message = searchResult.evidence_found
        ? searchResult.answer || `${searchResult.count} belegte Fundstelle${searchResult.count===1?'':'n'} im lokalen Wissensraum gefunden.`
        : searchResult.answer || `Für „${value}“ wurde in den fertig verarbeiteten Dokumenten kein belastbarer Beleg gefunden.`;
    } catch (error) { message = error instanceof Error ? error.message : 'Die lokale Suche ist fehlgeschlagen.'; }
    finally { searching = false; }
  }
  async function loadDocuments() { try { documents = await fetchDocuments(); } catch (error) { documents = []; importMessage = error instanceof Error ? error.message : 'Dokumentliste konnte nicht geladen werden.'; } }
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
    } finally {
      deletingId = null;
    }
  }
  async function openDocument(item: DocumentItem) {
    try { selectedDocument = await fetchDocument(item.id); }
    catch (error) { importMessage = error instanceof Error ? error.message : 'Details konnten nicht geladen werden.'; }
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
    <button class="launch" on:click={checkCore}>{health ? 'Core verbunden' : checking ? 'Prüfe Core' : 'Core starten'} <span>›</span></button>
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
          <div class="document-list">{#each documents as item}<article><b>{item.type}</b><div><h3>{item.name}</h3><p>{(Number(item.size) || 0)/1024 < 0.1 ? '0,0' : ((Number(item.size) || 0)/1024).toFixed(1)} KB · {(Number(item.character_count ?? item.extracted_chars) || 0).toLocaleString('de-DE')} Zeichen · {item.sha256?.slice(0,12) || '–'}…</p>{#if item.error_message}<small class="document-error">{item.error_message}</small>{/if}</div><div class="document-actions"><span class:failed={item.status === 'failed' || item.status === 'unsupported'}>{statusLabel(item.status)}</span><div><button type="button" on:click={() => openDocument(item)}>Details / Öffnen</button><button type="button" on:click={() => processDocument(item)} disabled={processingId === item.id}>{processingId === item.id ? 'Verarbeite …' : 'Neu verarbeiten'}</button><button class="danger" type="button" on:click={() => removeDocument(item)} disabled={deletingId === item.id}>{deletingId === item.id ? 'Entferne …' : 'Löschen'}</button></div></div></article>{/each}</div>
        {/if}
      </div>
    </section>

    {#if selectedDocument}
      <div class="document-modal">
        <div class="document-modal-card" role="dialog" aria-modal="true" aria-label="Dokumentdetails" tabindex="-1">
          <button class="modal-close" aria-label="Schließen" on:click={() => selectedDocument = null}>×</button>
          <p class="eyebrow">DOKUMENTDETAILS</p><h2>{selectedDocument.name}</h2>
          <dl><div><dt>Status</dt><dd>{statusLabel(selectedDocument.status)}</dd></div><div><dt>Größe</dt><dd>{((Number(selectedDocument.size) || 0)/1024).toFixed(1)} KB</dd></div><div><dt>Zeichen</dt><dd>{(Number(selectedDocument.character_count ?? selectedDocument.extracted_chars) || 0).toLocaleString('de-DE')}</dd></div><div><dt>SHA-256</dt><dd>{selectedDocument.sha256}</dd></div></dl>
          {#if selectedDocument.error_message}<p class="document-error">{selectedDocument.error_message}</p>{/if}
          <h3>Extrahierter Text</h3><pre>{selectedDocument.content || 'Kein extrahierter Text verfügbar.'}</pre>
        </div>
      </div>
    {/if}

    <section class="workspace" id="chat">
      <div class="workspace-copy"><p class="eyebrow">BELEGTE LOKALE SUCHE</p><h2>Frag dein<br/><span>Wissen.</span></h2><p>LumOS durchsucht ausschließlich deine freigegebenen lokalen Dokumente und zeigt jede verwendete Fundstelle offen an.</p></div>
      <div class="chat-card">
        <div class="chat-head"><span>LUMOS / KI-CHAT</span><span class="state"><i class:online={health}></i>{health?'CORE BEREIT':'CORE OFFLINE'}</span></div>
        <form on:submit|preventDefault={submitQuery}><textarea bind:value={query} placeholder="Was möchtest du in deinen Dokumenten finden?"></textarea><button type="submit" disabled={searching}>{searching?'Suche läuft …':'Lokal suchen'} <span>›</span></button></form>
        <div class="answer"><b>L</b><p>{message}</p></div>
        {#if searchResult?.evidence_found}<div class="sources"><div class="sources-head">QUELLEN / {searchResult.count} FUNDSTELLEN</div>{#each searchResult.hits as hit, index}<article><b>[{index+1}]</b><div><h3>{hit.document_name}{hit.page ? ` · Seite ${hit.page}` : ` · ${hit.section}`} · Trefferwert {hit.score.toFixed(2)}</h3><p>{hit.excerpt}</p></div></article>{/each}</div>{/if}
      </div>
    </section>

    <section class="status-section">
      <p class="eyebrow">ENTWICKLUNGSSTATUS</p><h2>Die Basis steht.<br/><span>Jetzt wird LumOS intelligent.</span></h2>
      <div class="steps"><div class="done"><b>01</b><span>Oberfläche</span><small>BEREIT</small></div><div class:done={health}><b>02</b><span>Lokaler Core</span><small>{health?'BEREIT':'PRÜFEN'}</small></div><div class="done"><b>03</b><span>Dokumentaufnahme</span><small>BEREIT</small></div><div class="done"><b>04</b><span>Textextraktion & Suche</span><small>BEREIT</small></div><div><b>05</b><span>Lokales KI-Modell</span><small>ALS NÄCHSTES</small></div></div>
    </section>
  </main>
  <footer><div><b>LumOS</b><small>LOKAL KI OFFICE</small></div><span>Studio M 360 · Development & Consulting</span><span>LOCAL FIRST · OFFLINE FIRST</span></footer>
</div>
