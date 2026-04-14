<!--
  M4: right sidebar showing Outline (TOC) and Bookmarks tabs.
  Width: 240px — replaces ThumbStrip in the flex layout when active.
-->
<script>
  import { createEventDispatcher } from 'svelte';

  export let outline     = [];   // [[level, title, page_1indexed], ...]
  export let bookmarks   = [];   // [{id, doc_id, page, label, created_at}, ...]
  export let currentPage = 1;

  const dispatch = createEventDispatcher();
  let tab = outline.length > 0 ? 'toc' : 'bookmarks';
</script>

<div class="panel">
  <div class="tabs">
    {#if outline.length > 0}
      <button class="tab" class:active={tab === 'toc'} on:click={() => (tab = 'toc')}>
        Outline
      </button>
    {/if}
    <button class="tab" class:active={tab === 'bookmarks'} on:click={() => (tab = 'bookmarks')}>
      Bookmarks {bookmarks.length > 0 ? `(${bookmarks.length})` : ''}
    </button>
    <button class="close" on:click={() => dispatch('close')} title="Close (Esc)">✕</button>
  </div>

  <div class="content">
    {#if tab === 'toc'}
      {#if outline.length === 0}
        <p class="empty">No outline in this document.</p>
      {:else}
        {#each outline as [level, title, pg]}
          <button
            class="toc-item"
            class:current={pg === currentPage}
            style="padding-left:{(level - 1) * 14 + 10}px"
            on:click={() => dispatch('go', pg)}
            title="p. {pg}"
          >
            <span class="toc-title">{title}</span>
            <span class="toc-pg">{pg}</span>
          </button>
        {/each}
      {/if}
    {:else}
      {#if bookmarks.length === 0}
        <p class="empty">No bookmarks yet — press <kbd>B</kbd> to add one.</p>
      {:else}
        {#each bookmarks as bm (bm.id)}
          <div class="bm-row" class:current={bm.page === currentPage}>
            <button class="bm-go" on:click={() => dispatch('go', bm.page)}>
              <span class="bm-page">p. {bm.page}</span>
              {#if bm.label}<span class="bm-label">{bm.label}</span>{/if}
            </button>
            <button
              class="bm-del"
              on:click={() => dispatch('delete-bookmark', bm.id)}
              title="Remove bookmark"
            >✕</button>
          </div>
        {/each}
      {/if}
    {/if}
  </div>
</div>

<style>
  .panel {
    width: 240px;
    flex: 0 0 240px;
    display: flex;
    flex-direction: column;
    background: #161616;
    border-left: 1px solid #262626;
    overflow: hidden;
  }

  /* ── Tabs bar ── */
  .tabs {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 6px 6px 0;
    border-bottom: 1px solid #262626;
    flex-shrink: 0;
  }
  .tab {
    flex: 1;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: #666;
    font-size: .72rem;
    padding: 5px 6px 7px;
    cursor: pointer;
    transition: color 80ms, border-color 80ms;
    white-space: nowrap;
  }
  .tab:hover  { color: #aaa; }
  .tab.active { color: #e0e0e0; border-bottom-color: #3b82f6; }

  .close {
    background: none;
    border: none;
    color: #555;
    font-size: .75rem;
    cursor: pointer;
    padding: 4px 6px;
    margin-left: auto;
    transition: color 80ms;
  }
  .close:hover { color: #ccc; }

  /* ── Scrollable content ── */
  .content {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: thin;
    scrollbar-color: #333 transparent;
    padding: 4px 0;
  }

  .empty {
    color: #555;
    font-size: .78rem;
    padding: 16px 12px;
    line-height: 1.5;
  }
  kbd {
    background: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 1px 4px;
    font-size: .7rem;
  }

  /* ── TOC items ── */
  .toc-item {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    padding-right: 10px;
    padding-top: 5px;
    padding-bottom: 5px;
    background: none;
    border: none;
    color: #999;
    font-size: .76rem;
    cursor: pointer;
    text-align: left;
    transition: background 60ms, color 60ms;
  }
  .toc-item:hover  { background: #1f1f1f; color: #ddd; }
  .toc-item.current { color: #3b82f6; }

  .toc-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .toc-pg    { flex-shrink: 0; color: #555; font-size: .68rem; }
  .toc-item.current .toc-pg { color: #2563eb; }

  /* ── Bookmark rows ── */
  .bm-row {
    display: flex;
    align-items: center;
    padding: 0 4px 0 10px;
    transition: background 60ms;
  }
  .bm-row:hover   { background: #1f1f1f; }
  .bm-row.current { background: #1a2035; }

  .bm-go {
    flex: 1;
    background: none;
    border: none;
    color: #aaa;
    font-size: .76rem;
    cursor: pointer;
    text-align: left;
    padding: 7px 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .bm-row.current .bm-go { color: #93c5fd; }
  .bm-page  { font-weight: 600; }
  .bm-label { color: #666; font-size: .68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .bm-del {
    background: none;
    border: none;
    color: #444;
    font-size: .7rem;
    cursor: pointer;
    padding: 4px 6px;
    transition: color 80ms;
    flex-shrink: 0;
  }
  .bm-del:hover { color: #e55; }
</style>
