<script>
  import { createEventDispatcher } from 'svelte';
  export let doc;
  export let allTags = [];   // [{id, name}] — passed from Gallery for tag editing

  const dispatch = createEventDispatcher();
  let coverLoaded = false;
</script>

<button class="card" on:click={() => dispatch('open', doc)}>
  <div class="cover-wrap">
    {#if doc.blurhash}
      <img class="blur" src={doc.blurhash} alt="" aria-hidden="true" />
    {/if}
    <img
      class="cover"
      class:visible={coverLoaded}
      src="/cache/covers/{doc.hash}.webp"
      alt={doc.title}
      on:load={() => (coverLoaded = true)}
    />
    {#if doc.status !== 'ready'}
      <div class="status-badge">{doc.status}</div>
    {/if}
  </div>

  <div class="meta">
    <div class="title">{doc.title}</div>
    {#if doc.author}
      <div class="author">{doc.author}</div>
    {/if}
    {#if doc.progress_pct > 0}
      <div class="bar-wrap">
        <div class="bar-fill" style="width:{doc.progress_pct}%"></div>
      </div>
    {/if}

    <!-- Delete button -->
    <button
      class="btn-delete"
      on:click|stopPropagation={() => dispatch('delete', doc)}
      title="Delete document"
    >✕</button>

    <!-- Tag chips + edit button -->
    <div class="tag-row">
      {#each (doc.tags ?? []) as tag}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <span
          class="tag-chip"
          on:click|stopPropagation={() => dispatch('filter-tag', tag)}
          title="Filter by {tag}"
        >{tag}</span>
      {/each}
      <button
        class="tag-edit"
        on:click|stopPropagation={() => dispatch('edit-tags', doc)}
        title="Edit tags"
      >⊕</button>
    </div>
  </div>
</button>

<style>
  .card {
    background: #1c1c1c;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    text-align: left;
    color: inherit;
    width: 100%;
    transition: border-color 100ms, transform 100ms;
  }
  .card:hover { border-color: #444; transform: translateY(-2px); }
  .card:active { transform: translateY(0); }

  .cover-wrap {
    position: relative;
    aspect-ratio: 3 / 4;
    overflow: hidden;
    background: #222;
  }
  .blur {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    filter: blur(12px);
    transform: scale(1.1);
  }
  .cover {
    position: relative;
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition: opacity 80ms;
  }
  .cover.visible { opacity: 1; }

  .status-badge {
    position: absolute;
    bottom: 6px;
    left: 6px;
    background: rgba(0,0,0,.7);
    color: #f59e0b;
    font-size: .65rem;
    padding: 2px 6px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: .05em;
  }

  .meta { padding: 8px; }
  .title {
    font-size: .8rem;
    line-height: 1.35;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .author {
    font-size: .7rem;
    color: #666;
    margin-top: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .bar-wrap {
    height: 3px;
    background: #2a2a2a;
    border-radius: 2px;
    margin-top: 6px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    background: #3b82f6;
    border-radius: 2px;
    transition: width 300ms;
  }

  /* ── Tags ── */
  .tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    margin-top: 6px;
    align-items: center;
  }
  .tag-chip {
    font-size: .62rem;
    background: #252525;
    border: 1px solid #333;
    border-radius: 3px;
    padding: 1px 5px;
    color: #888;
    cursor: pointer;
    white-space: nowrap;
    transition: background 80ms, color 80ms;
  }
  .tag-chip:hover { background: #2e3a52; color: #93c5fd; border-color: #3b82f6; }

  .btn-delete {
    position: absolute;
    top: 6px;
    right: 6px;
    background: rgba(0,0,0,.55);
    border: none;
    border-radius: 50%;
    color: #888;
    font-size: .65rem;
    width: 20px;
    height: 20px;
    line-height: 1;
    cursor: pointer;
    opacity: 0;
    transition: opacity 100ms, color 80ms, background 80ms;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card:hover .btn-delete { opacity: 1; }
  .btn-delete:hover { color: #fff; background: rgba(220,38,38,.8); }

  .tag-edit {
    background: none;
    border: 1px dashed #333;
    border-radius: 3px;
    color: #555;
    font-size: .65rem;
    padding: 1px 4px;
    cursor: pointer;
    line-height: 1.2;
    transition: border-color 80ms, color 80ms;
  }
  .tag-edit:hover { border-color: #3b82f6; color: #93c5fd; }
</style>
