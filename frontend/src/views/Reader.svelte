<script>
  import { onMount, onDestroy } from 'svelte';
  import ThumbStrip from '../components/ThumbStrip.svelte';
  import { getDoc, updateProgress } from '../lib/api.js';

  export let docId;
  export let initialPage = 1;

  let doc = null;
  let page = initialPage;
  let loading = true;
  let imgLoaded = false;
  let progressTimer = null;
  let showStrip = true;

  // Derived
  $: padded = (n) => String(n).padStart(4, '0');
  $: pageUrl = doc ? `/cache/pages/${doc.hash}/screen/${padded(page)}.webp` : '';
  $: atFirst = page <= 1;
  $: atLast  = doc ? page >= doc.page_count : false;

  onMount(async () => {
    doc = await getDoc(docId);
    page = Math.max(1, Math.min(initialPage, doc.page_count));
    loading = false;
    preload();
    window.addEventListener('keydown', handleKey);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKey);
    clearTimeout(progressTimer);
  });

  function goTo(n) {
    if (!doc) return;
    const p = Math.max(1, Math.min(n, doc.page_count));
    if (p === page) return;
    page = p;
    imgLoaded = false;
    location.hash = `#/r/${docId}/${page}`;
    scheduleProgress();
    preload();
  }

  function preload() {
    if (!doc) return;
    for (const n of [page + 1, page + 2, page - 1]) {
      if (n >= 1 && n <= doc.page_count) {
        const img = new Image();
        img.src = `/cache/pages/${doc.hash}/screen/${padded(n)}.webp`;
      }
    }
  }

  function scheduleProgress() {
    clearTimeout(progressTimer);
    progressTimer = setTimeout(() => updateProgress(docId, page), 300);
  }

  function handleKey(e) {
    // Don't steal keys when typing in an input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    switch (e.key) {
      case 'ArrowRight': case 'PageDown': case ' ':
        e.preventDefault(); goTo(page + 1); break;
      case 'ArrowLeft': case 'PageUp':
        e.preventDefault(); goTo(page - 1); break;
      case 'Home': e.preventDefault(); goTo(1); break;
      case 'End':  e.preventDefault(); goTo(doc?.page_count ?? 1); break;
      case 'f': case 'F': toggleFullscreen(); break;
      case 'g': case 'G': promptGoTo(); break;
      case 't': case 'T': showStrip = !showStrip; break;
      case 'Escape':
        if (document.fullscreenElement) document.exitFullscreen();
        break;
    }
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  }

  function promptGoTo() {
    const raw = prompt(`Go to page (1–${doc?.page_count}):`);
    const n = parseInt(raw ?? '', 10);
    if (!isNaN(n)) goTo(n);
  }
</script>

{#if loading}
  <div class="loading">Loading…</div>
{:else}
<div class="reader">

  <!-- ── Toolbar ── -->
  <div class="toolbar">
    <a href="#/" class="back">← Library</a>
    <span class="title">{doc.title}</span>

    <div class="nav">
      <button on:click={() => goTo(page - 1)} disabled={atFirst} title="Previous (←)">‹</button>
      <button class="page-input-wrap" on:click={promptGoTo} title="Jump to page (G)">
        <span>{page}</span><span class="of">/ {doc.page_count}</span>
      </button>
      <button on:click={() => goTo(page + 1)} disabled={atLast} title="Next (→)">›</button>
    </div>

    <div class="toolbar-right">
      <button class="icon-btn" on:click={() => showStrip = !showStrip} title="Toggle strip (T)">
        ☰
      </button>
      <button class="icon-btn" on:click={toggleFullscreen} title="Fullscreen (F)">
        ⛶
      </button>
    </div>
  </div>

  <!-- ── Main area ── -->
  <div class="body">

    <!-- Page display — click advances to next page -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="page-area" on:click={() => goTo(page + 1)}>
      <!-- Blur placeholder shown while real image loads -->
      {#if doc.blurhash}
        <img
          class="page-blur"
          class:hidden={imgLoaded}
          src={doc.blurhash}
          alt=""
          aria-hidden="true"
        />
      {/if}
      <img
        class="page-img"
        class:visible={imgLoaded}
        src={pageUrl}
        alt="Page {page} of {doc.title}"
        on:load={() => (imgLoaded = true)}
      />
    </div>

    <!-- Thumb strip -->
    {#if showStrip}
      <ThumbStrip {doc} currentPage={page} on:go={(e) => goTo(e.detail)} />
    {/if}

  </div>
</div>
{/if}

<style>
  .loading {
    display: flex; align-items: center; justify-content: center;
    height: 100vh; color: #555; font-size: .9rem;
  }

  .reader {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    background: #0d0d0d;
  }

  /* ── Toolbar ── */
  .toolbar {
    flex: 0 0 46px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 14px;
    background: #181818;
    border-bottom: 1px solid #262626;
    user-select: none;
    z-index: 10;
  }

  .back {
    font-size: .8rem;
    color: #666;
    white-space: nowrap;
    padding: 4px 6px;
    border-radius: 4px;
    transition: color 100ms;
  }
  .back:hover { color: #ccc; }

  .title {
    flex: 1;
    font-size: .8rem;
    color: #aaa;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .nav {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .nav button {
    background: none;
    border: 1px solid #2e2e2e;
    color: #ccc;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 3px 8px;
    transition: border-color 80ms, color 80ms;
  }
  .nav button:hover:not(:disabled) { border-color: #555; color: #fff; }
  .nav button:disabled { opacity: .28; cursor: default; }

  .page-input-wrap {
    min-width: 76px;
    text-align: center;
    font-size: .78rem;
    cursor: pointer;
    padding: 3px 8px;
    white-space: nowrap;
  }
  .of { color: #555; margin-left: 3px; }

  .toolbar-right {
    display: flex;
    gap: 4px;
    margin-left: 4px;
  }
  .icon-btn {
    background: none;
    border: 1px solid #2e2e2e;
    color: #888;
    border-radius: 4px;
    cursor: pointer;
    padding: 3px 7px;
    font-size: .85rem;
    transition: color 80ms, border-color 80ms;
  }
  .icon-btn:hover { color: #ccc; border-color: #555; }

  /* ── Body ── */
  .body {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  .page-area {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    cursor: pointer;
    position: relative;
    background: #0d0d0d;
  }

  .page-blur {
    position: absolute;
    max-height: 96%;
    max-width: 96%;
    object-fit: contain;
    filter: blur(20px);
    transform: scale(1.05);
    opacity: 0.4;
    transition: opacity 80ms;
  }
  .page-blur.hidden { opacity: 0; }

  .page-img {
    position: relative;
    max-height: 96%;
    max-width: 96%;
    object-fit: contain;
    opacity: 0;
    /* No transition — instantaneous swap IS the feature */
  }
  .page-img.visible { opacity: 1; }
</style>
