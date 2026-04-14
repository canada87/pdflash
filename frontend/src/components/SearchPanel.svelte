<!--
  M4: in-document full-text search overlay.
  Positioned absolute within .page-area (top-right corner).
  Results use FTS5 snippets from the backend (contain <b> highlight tags).
-->
<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import { search } from '../lib/api.js';

  export let doc;

  const dispatch = createEventDispatcher();

  let q       = '';
  let results = [];
  let busy    = false;
  let error   = false;
  let timer   = null;
  let input;

  onMount(() => input?.focus());

  // Debounced search triggered on every q change
  $: {
    clearTimeout(timer);
    error = false;
    if (q.trim().length >= 2) {
      busy = true;
      timer = setTimeout(async () => {
        try {
          results = await search(q.trim(), doc.id, 60);
        } catch {
          results = [];
          error = true;
        }
        busy = false;
      }, 300);
    } else {
      results = [];
      busy = false;
    }
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="panel" on:click|stopPropagation>
  <div class="header">
    <input
      bind:this={input}
      bind:value={q}
      type="search"
      placeholder="Search in document…"
      class="input"
      autocomplete="off"
    />
    <button class="close" on:click={() => dispatch('close')} title="Close (Esc)">✕</button>
  </div>

  {#if busy}
    <div class="hint">Searching…</div>
  {:else if error}
    <div class="hint err">Search error — try simpler terms.</div>
  {:else if q.trim().length >= 2 && results.length === 0}
    <div class="hint">No results.</div>
  {:else if results.length > 0}
    <div class="results">
      {#each results as r}
        <button class="result" on:click={() => dispatch('go', r.page)}>
          <span class="pg">p.{r.page}</span>
          <!-- eslint-disable-next-line svelte/no-at-html-tags -->
          <span class="snip">{@html r.snippet}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .panel {
    position: absolute;
    top: 10px;
    right: 10px;
    width: 310px;
    max-height: calc(100% - 20px);
    background: #1c1c1c;
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    box-shadow: 0 8px 32px rgba(0,0,0,.6);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    z-index: 30;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 8px 8px 12px;
    border-bottom: 1px solid #262626;
    flex-shrink: 0;
  }

  .input {
    flex: 1;
    background: #111;
    border: 1px solid #333;
    border-radius: 5px;
    color: #e0e0e0;
    font-size: .82rem;
    padding: 5px 8px;
    outline: none;
  }
  .input:focus { border-color: #3b82f6; }
  /* Remove browser's default search "×" button */
  .input::-webkit-search-cancel-button { display: none; }

  .close {
    background: none;
    border: none;
    color: #555;
    font-size: .75rem;
    cursor: pointer;
    padding: 4px 6px;
    transition: color 80ms;
    flex-shrink: 0;
  }
  .close:hover { color: #ccc; }

  .hint {
    padding: 10px 14px;
    color: #555;
    font-size: .78rem;
  }
  .hint.err { color: #e55; }

  .results {
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: #333 transparent;
  }

  .result {
    display: flex;
    align-items: baseline;
    gap: 8px;
    width: 100%;
    padding: 7px 12px;
    background: none;
    border: none;
    color: #aaa;
    font-size: .78rem;
    cursor: pointer;
    text-align: left;
    transition: background 60ms;
  }
  .result:hover { background: #252525; color: #ddd; }

  .pg {
    flex-shrink: 0;
    font-weight: 700;
    color: #3b82f6;
    font-size: .72rem;
    min-width: 32px;
  }

  .snip {
    flex: 1;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.4;
    color: #999;
  }

  /* Highlight from FTS5 snippet */
  .snip :global(b) {
    color: #fbbf24;
    font-weight: 600;
  }
</style>
