<script>
  import { onMount, onDestroy } from 'svelte';
  import DocCard from '../components/DocCard.svelte';
  import { getDocs, getContinueReading, uploadDoc,
           getTags, createTag, deleteTag, addDocTag, removeDocTag } from '../lib/api.js';

  let docs          = [];
  let continueReading = [];
  let allTags       = [];
  let loading       = true;
  let uploading     = false;
  let es;

  // ── Filter + sort state ───────────────────────────────────────────────────
  let sort      = 'recent';   // 'recent' | 'title' | 'progress'
  let activeTag = null;       // string tag name, or null = All

  const SORTS = [
    { key: 'recent',   label: 'Recent'   },
    { key: 'title',    label: 'A–Z'      },
    { key: 'progress', label: 'Progress' },
  ];

  // ── Tag management modal ──────────────────────────────────────────────────
  let editingDoc  = null;    // doc being tag-edited
  let newTagName  = '';

  // ── Load ──────────────────────────────────────────────────────────────────

  async function reload() {
    const params = { sort };
    if (activeTag) params.tag = activeTag;
    [docs, continueReading, allTags] = await Promise.all([
      getDocs(params),
      getContinueReading(),
      getTags(),
    ]);
    loading = false;
    // If the active tag was deleted, clear it
    if (activeTag && !allTags.some(t => t.name === activeTag)) activeTag = null;
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

  // ── Sort / filter ─────────────────────────────────────────────────────────

  function setSort(s) {
    sort = s;
    reload();
  }

  function setTag(name) {
    activeTag = name;
    reload();
  }

  // ── Upload ────────────────────────────────────────────────────────────────

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

  // ── Tag management modal ──────────────────────────────────────────────────

  function openTagModal(doc) {
    editingDoc = doc;
    newTagName = '';
  }

  function closeTagModal() {
    editingDoc = null;
    newTagName = '';
  }

  async function toggleDocTag(tag, checked) {
    if (!editingDoc) return;
    if (checked) {
      await addDocTag(editingDoc.id, tag.id);
      editingDoc = { ...editingDoc, tags: [...(editingDoc.tags ?? []), tag.name] };
    } else {
      await removeDocTag(editingDoc.id, tag.id);
      editingDoc = { ...editingDoc, tags: (editingDoc.tags ?? []).filter(n => n !== tag.name) };
    }
    reload();  // refresh gallery cards
  }

  async function addNewTag() {
    const name = newTagName.trim();
    if (!name) return;
    const tag = await createTag(name);
    newTagName = '';
    await reload();
    // Auto-attach the new tag to the doc being edited
    if (editingDoc) {
      await addDocTag(editingDoc.id, tag.id);
      editingDoc = { ...editingDoc, tags: [...(editingDoc.tags ?? []), tag.name] };
      reload();
    }
  }

  function onTagKeydown(e) {
    if (e.key === 'Enter') addNewTag();
    if (e.key === 'Escape') closeTagModal();
  }

  async function removeTagGlobal(tag) {
    if (!confirm(`Delete tag "${tag.name}" from all documents?`)) return;
    await deleteTag(tag.id);
    if (activeTag === tag.name) activeTag = null;
    reload();
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
      <input type="file" accept=".pdf" multiple on:change={handleFileInput} style="display:none" />
    </label>
  </header>

  <!-- ── Sort + tag filter bar ── -->
  <div class="filter-bar">
    <div class="sort-group">
      {#each SORTS as s}
        <button
          class="sort-btn"
          class:active={sort === s.key}
          on:click={() => setSort(s.key)}
        >{s.label}</button>
      {/each}
    </div>

    {#if allTags.length > 0}
      <div class="tag-pills">
        <button class="pill" class:active={!activeTag} on:click={() => setTag(null)}>All</button>
        {#each allTags as tag}
          <button
            class="pill"
            class:active={activeTag === tag.name}
            on:click={() => setTag(tag.name)}
          >{tag.name}</button>
        {/each}
      </div>
    {/if}
  </div>

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
    <h2>
      Library
      {#if docs.length > 0}({docs.length}){/if}
      {#if activeTag}<span class="tag-badge">{activeTag}</span>{/if}
    </h2>
    {#if loading}
      <p class="hint">Loading…</p>
    {:else if docs.length === 0}
      <p class="hint">
        {activeTag ? `No documents with tag "${activeTag}".` : 'No documents yet — drop a PDF here or click Upload.'}
      </p>
    {:else}
      <div class="grid">
        {#each docs as doc (doc.id)}
          <DocCard
            {doc}
            {allTags}
            on:open={() => openDoc(doc)}
            on:filter-tag={(e) => setTag(e.detail)}
            on:edit-tags={(e) => openTagModal(e.detail)}
          />
        {/each}
      </div>
    {/if}
  </section>
</div>

<!-- ── Tag management modal ── -->
{#if editingDoc}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="backdrop" on:click={closeTagModal}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="modal" on:click|stopPropagation>
      <div class="modal-header">
        <span class="modal-title">Tags — <em>{editingDoc.title}</em></span>
        <button class="modal-close" on:click={closeTagModal}>✕</button>
      </div>

      <div class="modal-body">
        {#if allTags.length === 0}
          <p class="hint" style="padding:0">No tags yet. Create one below.</p>
        {:else}
          {#each allTags as tag}
            <label class="tag-row">
              <input
                type="checkbox"
                checked={(editingDoc.tags ?? []).includes(tag.name)}
                on:change={(e) => toggleDocTag(tag, e.target.checked)}
              />
              <span class="tag-name">{tag.name}</span>
              <button
                class="del-btn"
                on:click|stopPropagation={() => removeTagGlobal(tag)}
                title="Delete tag globally"
              >✕</button>
            </label>
          {/each}
        {/if}
      </div>

      <div class="modal-footer">
        <input
          class="tag-input"
          bind:value={newTagName}
          placeholder="New tag name…"
          on:keydown={onTagKeydown}
        />
        <button class="btn-add" on:click={addNewTag}>Add</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page {
    min-height: 100vh;
    overflow-y: auto;
    padding: 20px 24px 48px;
    max-width: 1600px;
    margin: 0 auto;
  }

  /* ── Header ── */
  header {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
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
  .btn-upload.busy  { background: #1d4ed8; pointer-events: none; }

  /* ── Filter bar ── */
  .filter-bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 22px;
    padding-bottom: 14px;
    border-bottom: 1px solid #1e1e1e;
  }

  .sort-group {
    display: flex;
    gap: 3px;
    flex-shrink: 0;
  }
  .sort-btn {
    background: none;
    border: 1px solid #2a2a2a;
    color: #666;
    border-radius: 5px;
    padding: 4px 10px;
    font-size: .75rem;
    cursor: pointer;
    transition: color 80ms, border-color 80ms, background 80ms;
  }
  .sort-btn:hover  { color: #ccc; border-color: #444; }
  .sort-btn.active { color: #e0e0e0; border-color: #3b82f6; background: rgba(59,130,246,.1); }

  .tag-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .pill {
    background: none;
    border: 1px solid #2a2a2a;
    color: #666;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: .72rem;
    cursor: pointer;
    transition: color 80ms, border-color 80ms, background 80ms;
  }
  .pill:hover  { color: #ccc; border-color: #444; }
  .pill.active { color: #93c5fd; border-color: #3b82f6; background: rgba(59,130,246,.12); }

  /* ── Sections ── */
  section { margin-bottom: 36px; }

  h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #555;
    margin-bottom: 14px;
  }
  .tag-badge {
    font-size: .68rem;
    background: rgba(59,130,246,.15);
    color: #93c5fd;
    border: 1px solid #3b82f6;
    border-radius: 10px;
    padding: 1px 8px;
    text-transform: none;
    letter-spacing: 0;
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

  /* ── Tag management modal ── */
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal {
    background: #1c1c1c;
    border: 1px solid #2e2e2e;
    border-radius: 10px;
    width: 340px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 16px 48px rgba(0,0,0,.7);
  }

  .modal-header {
    display: flex;
    align-items: center;
    padding: 14px 16px 12px;
    border-bottom: 1px solid #262626;
    gap: 8px;
    flex-shrink: 0;
  }
  .modal-title {
    flex: 1;
    font-size: .82rem;
    color: #aaa;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .modal-title em { color: #ccc; font-style: normal; }
  .modal-close {
    background: none;
    border: none;
    color: #555;
    cursor: pointer;
    font-size: .8rem;
    padding: 2px 6px;
    transition: color 80ms;
    flex-shrink: 0;
  }
  .modal-close:hover { color: #ccc; }

  .modal-body {
    overflow-y: auto;
    padding: 8px 6px;
    flex: 1;
    scrollbar-width: thin;
    scrollbar-color: #333 transparent;
  }

  .tag-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 10px;
    border-radius: 5px;
    cursor: pointer;
    transition: background 60ms;
  }
  .tag-row:hover { background: #252525; }

  .tag-row input[type="checkbox"] {
    accent-color: #3b82f6;
    cursor: pointer;
    flex-shrink: 0;
  }
  .tag-name { flex: 1; font-size: .82rem; color: #ccc; }

  .del-btn {
    background: none;
    border: none;
    color: #444;
    font-size: .7rem;
    cursor: pointer;
    padding: 2px 5px;
    transition: color 80ms;
    flex-shrink: 0;
  }
  .del-btn:hover { color: #e55; }

  .modal-footer {
    display: flex;
    gap: 6px;
    padding: 10px 12px 12px;
    border-top: 1px solid #262626;
    flex-shrink: 0;
  }
  .tag-input {
    flex: 1;
    background: #111;
    border: 1px solid #333;
    border-radius: 5px;
    color: #e0e0e0;
    font-size: .82rem;
    padding: 5px 8px;
    outline: none;
  }
  .tag-input:focus { border-color: #3b82f6; }
  .btn-add {
    background: #3b82f6;
    border: none;
    border-radius: 5px;
    color: #fff;
    font-size: .8rem;
    padding: 5px 12px;
    cursor: pointer;
    transition: background 80ms;
    flex-shrink: 0;
  }
  .btn-add:hover { background: #2563eb; }
</style>
