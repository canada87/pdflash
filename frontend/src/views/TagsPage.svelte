<script>
  import { onMount } from 'svelte';
  import { getTags, createTag, updateTag, deleteTag } from '../lib/api.js';

  const COLORS = [
    '#6b7280', '#ef4444', '#f97316', '#eab308',
    '#22c55e', '#14b8a6', '#3b82f6', '#8b5cf6',
    '#ec4899', '#a78bfa', '#06b6d4', '#84cc16',
  ];

  let tags    = [];
  let loading = true;

  $: roots    = tags.filter(t => t.parent_id === null).sort((a, b) => a.name.localeCompare(b.name));
  $: childMap = tags.reduce((m, t) => {
    if (t.parent_id !== null) (m[t.parent_id] ??= []).push(t);
    return m;
  }, {});

  // ── create form ──────────────────────────────────────────────────────────────
  let creating    = false;
  let newName     = '';
  let newColor    = COLORS[6];
  let newParentId = null;

  // ── edit form ────────────────────────────────────────────────────────────────
  let editId       = null;
  let editName     = '';
  let editColor    = '';
  let editParentId = null;

  async function load() {
    tags    = await getTags();
    loading = false;
  }

  onMount(load);

  function startCreate() {
    creating    = true;
    newName     = '';
    newColor    = COLORS[6];
    newParentId = null;
    editId      = null;
  }

  async function saveNew() {
    const name = newName.trim();
    if (!name) return;
    await createTag(name, newColor, newParentId);
    creating = false;
    await load();
  }

  function startEdit(tag) {
    editId       = tag.id;
    editName     = tag.name;
    editColor    = tag.color;
    editParentId = tag.parent_id;
    creating     = false;
  }

  function cancelEdit() { editId = null; }

  async function saveEdit() {
    const name = editName.trim();
    if (!name) return;
    await updateTag(editId, { name, color: editColor, parent_id: editParentId });
    editId = null;
    await load();
  }

  async function del(tag) {
    const children = childMap[tag.id] ?? [];
    const msg = children.length > 0
      ? `Delete "${tag.name}"? Its ${children.length} child tag(s) will become top-level.`
      : `Delete tag "${tag.name}"?`;
    if (!confirm(msg)) return;
    await deleteTag(tag.id);
    await load();
  }
</script>

<div class="page">
  <header>
    <a href="#/" class="back">← Library</a>
    <h1>Tag Management</h1>
    <div class="header-actions">
      <button class="btn-new" on:click={startCreate}>＋ New tag</button>
    </div>
  </header>

  <!-- ── Create form ── -->
  {#if creating}
    <div class="form-card">
      <div class="form-title">New tag</div>

      <label class="field">
        <span class="flabel">Name</span>
        <!-- svelte-ignore a11y-autofocus -->
        <input
          class="finput"
          bind:value={newName}
          placeholder="Tag name…"
          on:keydown={e => { if (e.key==='Enter') saveNew(); if (e.key==='Escape') creating=false; }}
          autofocus
        />
      </label>

      <label class="field">
        <span class="flabel">Parent tag <span class="opt">(optional)</span></span>
        <select class="finput" bind:value={newParentId}>
          <option value={null}>— none (top-level) —</option>
          {#each roots as r}
            <option value={r.id}>{r.name}</option>
          {/each}
        </select>
      </label>

      <div class="field">
        <span class="flabel">Color</span>
        <div class="palette">
          {#each COLORS as c}
            <button
              class="swatch"
              class:picked={newColor === c}
              style="background:{c}"
              on:click={() => newColor = c}
              title={c}
            >{newColor === c ? '✓' : ''}</button>
          {/each}
        </div>
      </div>

      <div class="form-actions">
        <button class="btn-save" on:click={saveNew}>Create</button>
        <button class="btn-cancel" on:click={() => creating = false}>Cancel</button>
      </div>
    </div>
  {/if}

  <!-- ── Tag list ── -->
  {#if loading}
    <p class="hint">Loading…</p>
  {:else if tags.length === 0 && !creating}
    <p class="hint">No tags yet. Click "New tag" to get started.</p>
  {:else}
    <div class="list">
      {#each roots as root}

        <!-- root tag row -->
        {#if editId === root.id}
          <div class="edit-row">
            <div class="form-title">Edit tag</div>
            <label class="field">
              <span class="flabel">Name</span>
              <input class="finput" bind:value={editName}
                on:keydown={e => { if (e.key==='Enter') saveEdit(); if (e.key==='Escape') cancelEdit(); }} />
            </label>
            <!-- tag with children can't become a child itself -->
            {#if !(childMap[root.id]?.length > 0)}
              <label class="field">
                <span class="flabel">Parent tag <span class="opt">(optional)</span></span>
                <select class="finput" bind:value={editParentId}>
                  <option value={null}>— none (top-level) —</option>
                  {#each roots.filter(r => r.id !== root.id) as r}
                    <option value={r.id}>{r.name}</option>
                  {/each}
                </select>
              </label>
            {/if}
            <div class="field">
              <span class="flabel">Color</span>
              <div class="palette">
                {#each COLORS as c}
                  <button class="swatch" class:picked={editColor===c} style="background:{c}"
                    on:click={() => editColor=c} title={c}>{editColor===c ? '✓' : ''}</button>
                {/each}
              </div>
            </div>
            <div class="form-actions">
              <button class="btn-save" on:click={saveEdit}>Save</button>
              <button class="btn-cancel" on:click={cancelEdit}>Cancel</button>
            </div>
          </div>
        {:else}
          <div class="row root-row">
            <span class="dot" style="background:{root.color}"></span>
            <span class="name">{root.name}</span>
            <span class="count">{(childMap[root.id]?.length) || ''}</span>
            <button class="icon-btn" on:click={() => startEdit(root)} title="Edit">✎</button>
            <button class="icon-btn danger" on:click={() => del(root)} title="Delete">✕</button>
          </div>
        {/if}

        <!-- children -->
        {#each (childMap[root.id] ?? []).sort((a,b) => a.name.localeCompare(b.name)) as child}
          {#if editId === child.id}
            <div class="edit-row child-edit">
              <div class="form-title">Edit tag</div>
              <label class="field">
                <span class="flabel">Name</span>
                <input class="finput" bind:value={editName}
                  on:keydown={e => { if (e.key==='Enter') saveEdit(); if (e.key==='Escape') cancelEdit(); }} />
              </label>
              <label class="field">
                <span class="flabel">Parent tag <span class="opt">(optional)</span></span>
                <select class="finput" bind:value={editParentId}>
                  <option value={null}>— none (top-level) —</option>
                  {#each roots.filter(r => r.id !== child.id) as r}
                    <option value={r.id}>{r.name}</option>
                  {/each}
                </select>
              </label>
              <div class="field">
                <span class="flabel">Color</span>
                <div class="palette">
                  {#each COLORS as c}
                    <button class="swatch" class:picked={editColor===c} style="background:{c}"
                      on:click={() => editColor=c} title={c}>{editColor===c ? '✓' : ''}</button>
                  {/each}
                </div>
              </div>
              <div class="form-actions">
                <button class="btn-save" on:click={saveEdit}>Save</button>
                <button class="btn-cancel" on:click={cancelEdit}>Cancel</button>
              </div>
            </div>
          {:else}
            <div class="row child-row">
              <span class="indent"></span>
              <span class="dot" style="background:{child.color}"></span>
              <span class="name">{child.name}</span>
              <button class="icon-btn" on:click={() => startEdit(child)} title="Edit">✎</button>
              <button class="icon-btn danger" on:click={() => del(child)} title="Delete">✕</button>
            </div>
          {/if}
        {/each}

      {/each}
    </div>
  {/if}
</div>

<style>
  .page {
    height: 100vh;
    overflow-y: auto;
    padding: 20px 24px 48px;
    max-width: 680px;
    margin: 0 auto;
  }

  /* ── Header ── */
  header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 28px;
  }

  .back {
    color: #555;
    text-decoration: none;
    font-size: .82rem;
    flex-shrink: 0;
    transition: color 80ms;
  }
  .back:hover { color: #ccc; }

  h1 {
    font-size: 1rem;
    font-weight: 600;
    flex: 1;
    color: #e0e0e0;
    margin: 0;
  }

  .header-actions { display: flex; gap: 8px; }

  .btn-new {
    background: #1e1e1e;
    border: 1px solid #333;
    color: #aaa;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: .78rem;
    cursor: pointer;
    transition: border-color 80ms, color 80ms;
  }
  .btn-new:hover { border-color: #3b82f6; color: #93c5fd; }

  /* ── Form card (create) ── */
  .form-card {
    background: #1a1a1a;
    border: 1px solid #2e2e2e;
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 24px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .form-title {
    font-size: .7rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #555;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .flabel {
    font-size: .7rem;
    color: #555;
    text-transform: uppercase;
    letter-spacing: .06em;
  }

  .opt {
    text-transform: none;
    letter-spacing: 0;
    color: #3a3a3a;
  }

  .finput {
    background: #111;
    border: 1px solid #333;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: .85rem;
    padding: 7px 10px;
    outline: none;
    width: 100%;
    box-sizing: border-box;
  }
  .finput:focus { border-color: #3b82f6; }
  select.finput { cursor: pointer; }

  .palette {
    display: flex;
    gap: 7px;
    flex-wrap: wrap;
  }

  .swatch {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    font-size: .58rem;
    color: rgba(255,255,255,.9);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 100ms, border-color 100ms;
    flex-shrink: 0;
  }
  .swatch:hover  { transform: scale(1.18); }
  .swatch.picked { border-color: #fff; transform: scale(1.2); }

  .form-actions {
    display: flex;
    gap: 8px;
  }

  .btn-save {
    background: #3b82f6;
    border: none;
    border-radius: 6px;
    color: #fff;
    font-size: .8rem;
    padding: 6px 16px;
    cursor: pointer;
    transition: background 80ms;
  }
  .btn-save:hover { background: #2563eb; }

  .btn-cancel {
    background: none;
    border: 1px solid #333;
    border-radius: 6px;
    color: #666;
    font-size: .8rem;
    padding: 6px 14px;
    cursor: pointer;
    transition: color 80ms, border-color 80ms;
  }
  .btn-cancel:hover { color: #ccc; border-color: #555; }

  /* ── List ── */
  .list { display: flex; flex-direction: column; }

  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 10px;
    border-radius: 7px;
    transition: background 60ms;
  }
  .row:hover { background: #1a1a1a; }

  .root-row { margin-top: 4px; }

  .child-row { padding-left: 6px; }

  .indent {
    width: 18px;
    flex-shrink: 0;
    position: relative;
    align-self: stretch;
  }
  .indent::before {
    content: '';
    position: absolute;
    left: 12px;
    top: 50%;
    width: 8px;
    height: 1px;
    background: #333;
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .name {
    flex: 1;
    font-size: .85rem;
    color: #ccc;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .root-row .name { font-weight: 500; color: #e0e0e0; }

  .count {
    font-size: .7rem;
    color: #444;
    min-width: 16px;
    text-align: right;
    flex-shrink: 0;
  }

  .icon-btn {
    background: none;
    border: none;
    color: #444;
    font-size: .78rem;
    cursor: pointer;
    padding: 3px 6px;
    border-radius: 4px;
    transition: color 80ms, background 80ms;
    flex-shrink: 0;
    opacity: 0;
  }
  .row:hover .icon-btn { opacity: 1; }
  .icon-btn:hover { color: #aaa; background: #2a2a2a; }
  .icon-btn.danger:hover { color: #ef4444; background: rgba(239,68,68,.1); }

  /* ── Inline edit row ── */
  .edit-row {
    background: #1a1a1a;
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    padding: 14px 16px;
    margin: 4px 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .child-edit { margin-left: 30px; }

  .hint { color: #555; font-size: .875rem; }
</style>
