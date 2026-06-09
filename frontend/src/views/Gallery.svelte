<script>
  import { onMount, onDestroy } from 'svelte';
  import DocCard from '../components/DocCard.svelte';
  import { getDocs, uploadDoc,
           getTags, createTag, addDocTag, removeDocTag, deleteDoc } from '../lib/api.js';

  let docs    = [];
  let allTags = [];
  let loading   = true;
  let uploading = false;
  let es;

  // doc_id (number) → {title, pct}
  let processingDocs = {};

  // ── Filter + sort state ───────────────────────────────────────────────────
  let sort       = 'recent';  // 'recent' | 'title' | 'progress'
  let activeTags = new Set(); // Set<string> of active tag names
  let tagMode    = 'or';      // 'or' | 'and'

  const SORTS = [
    { key: 'recent',   label: 'Recent'   },
    { key: 'title',    label: 'A–Z'      },
    { key: 'progress', label: 'Progress' },
  ];

  // ── Tag assignment modal ──────────────────────────────────────────────────
  let editingDoc = null;
  let newTagName = '';

  // ── Derived: tags grouped by hierarchy ───────────────────────────────────
  $: tagRoots   = allTags.filter(t => t.parent_id === null);
  $: tagChildOf = id => allTags.filter(t => t.parent_id === id);

  // ── Load ──────────────────────────────────────────────────────────────────

  async function reload() {
    const params = { sort };
    if (activeTags.size > 0) {
      params.tags = [...activeTags].join(',');
      if (activeTags.size > 1) params.tag_mode = tagMode;
    }
    const [newDocs, newTagList] = await Promise.all([getDocs(params), getTags()]);
    docs    = newDocs;
    allTags = newTagList;
    loading = false;
    // prune stale active tags
    for (const name of activeTags) {
      if (!allTags.some(t => t.name === name)) activeTags.delete(name);
    }
    activeTags = activeTags;
  }

  onMount(async () => {
    reload();

    try {
      const indexing = await fetch('/api/docs/indexing').then(r => r.json());
      for (const d of indexing) {
        processingDocs[d.id] = { title: d.title, pct: 0 };
      }
      if (indexing.length) processingDocs = { ...processingDocs };
    } catch (_) {}

    es = new EventSource('/api/events');
    es.onmessage = (e) => {
      const ev = JSON.parse(e.data);
      if (ev.type === 'doc_progress') {
        processingDocs = { ...processingDocs, [ev.doc_id]: { title: ev.title, pct: ev.pct } };
      } else if (ev.type === 'doc_ready' || ev.type === 'doc_failed') {
        const { [ev.doc_id]: _, ...rest } = processingDocs;
        processingDocs = rest;
        reload();
      }
    };
  });

  onDestroy(() => es?.close());

  function openDoc(doc) {
    location.hash = `#/r/${doc.id}/${doc.last_page || 1}`;
  }

  // ── Sort / tag filter ─────────────────────────────────────────────────────

  function setSort(s) {
    sort = s;
    reload();
  }

  function toggleTag(name) {
    if (activeTags.has(name)) activeTags.delete(name);
    else activeTags.add(name);
    activeTags = activeTags;
    reload();
  }

  function clearTags() {
    activeTags = new Set();
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

  // ── Tag assignment modal ──────────────────────────────────────────────────

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
    reload();
  }

  async function addNewTag() {
    const name = newTagName.trim();
    if (!name) return;
    const tag = await createTag(name);
    newTagName = '';
    await reload();
    if (editingDoc) {
      await addDocTag(editingDoc.id, tag.id);
      editingDoc = { ...editingDoc, tags: [...(editingDoc.tags ?? []), tag.name] };
      reload();
    }
  }

  async function handleDelete(doc) {
    if (!confirm(`Delete "${doc.title}"?\nThis removes the document and all its cached data.`)) return;
    await deleteDoc(doc.id);
    reload();
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  function pillStyle(tag) {
    if (!activeTags.has(tag.name)) return '';
    const c = tag.color || '#3b82f6';
    return `color:${c};border-color:${c};background:${c}1a`;
  }

  function tagColor(name) {
    return allTags.find(t => t.name === name)?.color ?? '#6b7280';
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
        {#each tagRoots as cat}
          <button
            class="pill"
            class:active={activeTags.has(cat.name)}
            style={pillStyle(cat)}
            on:click={() => toggleTag(cat.name)}
          >{cat.name}</button>
          {#each tagChildOf(cat.id) as child}
            <button
              class="pill child-pill"
              class:active={activeTags.has(child.name)}
              style={pillStyle(child)}
              on:click={() => toggleTag(child.name)}
            >{child.name}</button>
          {/each}
        {/each}

        {#if activeTags.size > 1}
          <button
            class="mode-btn"
            on:click={() => { tagMode = tagMode === 'or' ? 'and' : 'or'; reload(); }}
          >{tagMode.toUpperCase()}</button>
        {/if}
        {#if activeTags.size > 0}
          <button class="clear-btn" on:click={clearTags} title="Clear filters">✕</button>
        {/if}
      </div>
    {/if}

    <a class="manage-link" href="#/tags">Manage tags</a>
  </div>

  {#if Object.keys(processingDocs).length > 0}
    <section class="processing">
      <h2>Processing</h2>
      {#each Object.entries(processingDocs) as [id, doc]}
        <div class="proc-row">
          <span class="proc-title">{doc.title}</span>
          <div class="proc-track">
            <div class="proc-fill" style="width:{doc.pct}%"></div>
          </div>
          <span class="proc-pct">{doc.pct}%</span>
        </div>
      {/each}
    </section>
  {/if}

  <section>
    <h2>
      Library
      {#if docs.length > 0}({docs.length}){/if}
      {#each [...activeTags] as name}
        {@const c = tagColor(name)}
        <span class="tag-badge" style="color:{c};border-color:{c};background:{c}1a">{name}</span>
      {/each}
      {#if activeTags.size > 1}
        <span class="mode-badge">{tagMode.toUpperCase()}</span>
      {/if}
    </h2>
    {#if loading}
      <p class="hint">Loading…</p>
    {:else if docs.length === 0}
      <p class="hint">
        {activeTags.size > 0 ? 'No documents match the selected tags.' : 'No documents yet — drop a PDF here or click Upload.'}
      </p>
    {:else}
      <div class="grid">
        {#each docs as doc (doc.id)}
          <DocCard
            {doc}
            {allTags}
            on:open={() => openDoc(doc)}
            on:filter-tag={(e) => toggleTag(e.detail)}
            on:edit-tags={(e) => openTagModal(e.detail)}
            on:delete={(e) => handleDelete(e.detail)}
          />
        {/each}
      </div>
    {/if}
  </section>
</div>

<!-- ── Tag assignment modal ── -->
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
          <p class="hint" style="padding:0 10px">No tags yet — <a href="#/tags" on:click={closeTagModal}>create some</a>.</p>
        {:else}
          {#each tagRoots as cat}
            <!-- category header -->
            <div class="modal-cat-header">
              <span class="modal-dot" style="background:{cat.color}"></span>
              <label class="tag-check">
                <input
                  type="checkbox"
                  checked={(editingDoc.tags ?? []).includes(cat.name)}
                  on:change={(e) => toggleDocTag(cat, e.target.checked)}
                />
                <span class="tag-name">{cat.name}</span>
              </label>
            </div>
            <!-- children -->
            {#each tagChildOf(cat.id) as child}
              <div class="tag-row child-tag-row">
                <span class="modal-dot" style="background:{child.color}"></span>
                <label class="tag-check">
                  <input
                    type="checkbox"
                    checked={(editingDoc.tags ?? []).includes(child.name)}
                    on:change={(e) => toggleDocTag(child, e.target.checked)}
                  />
                  <span class="tag-name">{child.name}</span>
                </label>
              </div>
            {/each}
          {/each}
        {/if}
      </div>

      <div class="modal-footer">
        <input
          class="tag-input"
          bind:value={newTagName}
          placeholder="Quick add tag…"
          on:keydown={e => { if (e.key==='Enter') addNewTag(); if (e.key==='Escape') closeTagModal(); }}
        />
        <button class="btn-add" on:click={addNewTag}>Add</button>
      </div>
      <div class="modal-manage">
        <a href="#/tags" on:click={closeTagModal}>Manage tags →</a>
      </div>
    </div>
  </div>
{/if}

<style>
  .page {
    height: 100vh;
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
    align-items: center;
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
  .pill:hover { color: #ccc; border-color: #444; }

  .child-pill {
    font-size: .68rem;
    padding: 2px 8px;
    opacity: .85;
  }

  .mode-btn {
    background: #1e1e1e;
    border: 1px solid #3b82f6;
    color: #3b82f6;
    border-radius: 5px;
    padding: 2px 8px;
    font-size: .65rem;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: .04em;
    transition: background 80ms;
  }
  .mode-btn:hover { background: rgba(59,130,246,.15); }

  .clear-btn {
    background: none;
    border: none;
    color: #555;
    font-size: .72rem;
    cursor: pointer;
    padding: 2px 5px;
    transition: color 80ms;
  }
  .clear-btn:hover { color: #ccc; }

  .manage-link {
    margin-left: auto;
    font-size: .72rem;
    color: #444;
    text-decoration: none;
    transition: color 80ms;
    flex-shrink: 0;
  }
  .manage-link:hover { color: #888; }

  /* ── Sections ── */
  section { margin-bottom: 36px; }

  h2 {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    font-size: .75rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #555;
    margin-bottom: 14px;
  }
  .tag-badge {
    font-size: .66rem;
    border: 1px solid;
    border-radius: 10px;
    padding: 1px 7px;
    text-transform: none;
    letter-spacing: 0;
  }
  .mode-badge {
    font-size: .6rem;
    font-weight: 700;
    color: #555;
    letter-spacing: .06em;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
    gap: 14px;
  }

  .hint { color: #555; font-size: .875rem; }
  .hint a { color: #3b82f6; }

  /* ── Processing section ── */
  .processing { margin-bottom: 28px; }

  .proc-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 5px 0;
  }
  .proc-title {
    flex: 1;
    font-size: .8rem;
    color: #aaa;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .proc-track {
    width: 160px;
    flex-shrink: 0;
    height: 4px;
    background: #222;
    border-radius: 2px;
    overflow: hidden;
  }
  .proc-fill {
    height: 100%;
    background: #3b82f6;
    border-radius: 2px;
    transition: width 300ms linear;
  }
  .proc-pct {
    font-size: .72rem;
    color: #555;
    width: 34px;
    text-align: right;
    flex-shrink: 0;
  }

  /* ── Tag assignment modal ── */
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
    width: 320px;
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

  .modal-cat-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 6px 1px;
    margin-top: 4px;
  }

  .tag-row {
    display: flex;
    align-items: center;
    gap: 6px;
    border-radius: 5px;
    transition: background 60ms;
    padding: 0 6px;
  }
  .tag-row:hover { background: #252525; }

  .child-tag-row { padding-left: 22px; }

  .modal-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .tag-check {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    padding: 5px 4px;
    cursor: pointer;
  }
  .tag-check input[type="checkbox"] {
    accent-color: #3b82f6;
    cursor: pointer;
    flex-shrink: 0;
  }
  .tag-name { font-size: .82rem; color: #ccc; }

  .modal-footer {
    display: flex;
    gap: 6px;
    padding: 10px 12px 8px;
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

  .modal-manage {
    padding: 6px 16px 10px;
    text-align: right;
    flex-shrink: 0;
  }
  .modal-manage a {
    font-size: .72rem;
    color: #444;
    text-decoration: none;
    transition: color 80ms;
  }
  .modal-manage a:hover { color: #93c5fd; }
</style>
