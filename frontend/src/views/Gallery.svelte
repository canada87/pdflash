<script>
  import { onMount, onDestroy } from 'svelte';
  import DocCard from '../components/DocCard.svelte';
  import { getDocs, getContinueReading, uploadDoc } from '../lib/api.js';

  let docs = [];
  let continueReading = [];
  let loading = true;
  let uploading = false;
  let es;

  async function reload() {
    [docs, continueReading] = await Promise.all([getDocs(), getContinueReading()]);
    loading = false;
  }

  onMount(() => {
    reload();
    es = new EventSource('/api/events');
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.type === 'doc_ready' || ev.type === 'doc_failed') reload();
    };
  });

  onDestroy(() => es?.close());

  function openDoc(doc) {
    location.hash = `#/r/${doc.id}/${doc.last_page || 1}`;
  }

  async function handleFileInput(e) {
    const files = [...e.target.files];
    if (!files.length) return;
    uploading = true;
    for (const f of files) {
      try { await uploadDoc(f); } catch (err) { console.error('Upload failed', err); }
    }
    uploading = false;
    e.target.value = '';
  }

  function handleDrop(e) {
    e.preventDefault();
    const files = [...e.dataTransfer.files].filter(f => f.name.endsWith('.pdf'));
    if (!files.length) return;
    uploading = true;
    Promise.all(files.map(f => uploadDoc(f).catch(console.error)))
      .then(() => { uploading = false; });
  }
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="page"
  on:dragover|preventDefault
  on:drop={handleDrop}
>
  <header>
    <span class="logo">⚡ pdflash</span>
    <label class="btn-upload" class:busy={uploading}>
      {uploading ? 'Uploading…' : '+ Upload PDF'}
      <input
        type="file"
        accept=".pdf"
        multiple
        on:change={handleFileInput}
        style="display:none"
      />
    </label>
  </header>

  {#if continueReading.length > 0}
    <section>
      <h2>Continue reading</h2>
      <div class="shelf">
        {#each continueReading as doc}
          <div class="shelf-item">
            <DocCard {doc} on:open={() => openDoc(doc)} />
          </div>
        {/each}
      </div>
    </section>
  {/if}

  <section>
    <h2>Library {docs.length > 0 ? `(${docs.length})` : ''}</h2>
    {#if loading}
      <p class="hint">Loading…</p>
    {:else if docs.length === 0}
      <p class="hint">No documents yet — drop a PDF here or click Upload.</p>
    {:else}
      <div class="grid">
        {#each docs as doc (doc.id)}
          <DocCard {doc} on:open={() => openDoc(doc)} />
        {/each}
      </div>
    {/if}
  </section>
</div>

<style>
  .page {
    height: 100vh;
    overflow-y: auto;
    padding: 20px 24px 48px;
    max-width: 1600px;
    margin: 0 auto;
  }

  header {
    display: flex;
    align-items: center;
    margin-bottom: 28px;
    gap: 12px;
  }
  .logo {
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: -.02em;
  }
  .btn-upload {
    margin-left: auto;
    padding: 7px 16px;
    background: #3b82f6;
    color: #fff;
    border-radius: 6px;
    cursor: pointer;
    font-size: .85rem;
    transition: background 120ms;
  }
  .btn-upload:hover { background: #2563eb; }
  .btn-upload.busy { background: #1d4ed8; pointer-events: none; }

  section { margin-bottom: 36px; }

  h2 {
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #555;
    margin-bottom: 14px;
  }

  .shelf {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    padding-bottom: 6px;
    scrollbar-width: thin;
    scrollbar-color: #333 transparent;
  }
  .shelf-item { flex: 0 0 140px; }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
    gap: 14px;
  }

  .hint { color: #555; font-size: .875rem; }
</style>
