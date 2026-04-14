<script>
  import { onMount, onDestroy } from 'svelte';
  import ThumbStrip from '../components/ThumbStrip.svelte';
  import TocPanel   from '../components/TocPanel.svelte';
  import SearchPanel from '../components/SearchPanel.svelte';
  import { getDoc, updateProgress, getBookmarks, createBookmark, deleteBookmark as apiDeleteBm, getPageImages } from '../lib/api.js';

  export let docId;
  export let initialPage = 1;

  let doc       = null;
  let page      = initialPage;
  let loading   = true;
  let imgLoaded = false;
  let progressTimer = null;

  // ── UI state ──────────────────────────────────────────────────────────────
  // panel: which right-side panel is open (null = none)
  let panel      = 'thumbs';   // null | 'thumbs' | 'toc'
  let showSearch = false;
  let doubleMode = false;

  // ── Zoom + pan ────────────────────────────────────────────────────────────
  let zoom  = 1.0;
  let panX  = 0;
  let panY  = 0;
  // Mouse state (not reactive — only read in handlers)
  let _md   = null;   // {x, y, panX, panY} snapshot on mousedown
  let _drag = false;  // whether current press has crossed drag threshold

  // ── Bookmarks ─────────────────────────────────────────────────────────────
  let bookmarks = [];

  // ── Embedded images modal ─────────────────────────────────────────────────
  let showImages    = false;
  let pageImages    = [];
  let imagesLoading = false;

  // ── Derived ───────────────────────────────────────────────────────────────
  $: step         = doubleMode ? 2 : 1;
  $: atFirst      = page <= 1;
  $: atLast       = doc ? page + step > doc.page_count : false;
  $: isBookmarked = bookmarks.some(b => b.page === page);
  $: outline      = (() => {
    try { return doc?.outline_json ? JSON.parse(doc.outline_json) : []; }
    catch { return []; }
  })();

  function pageUrl(n) {
    return doc ? `/cache/pages/${doc.hash}/screen/${String(n).padStart(4, '0')}.webp` : '';
  }

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  onMount(async () => {
    [doc, bookmarks] = await Promise.all([getDoc(docId), getBookmarks(docId)]);
    page = Math.max(1, Math.min(initialPage, doc.page_count));
    loading = false;
    preload();
    window.addEventListener('keydown', handleKey);
  });

  onDestroy(() => {
    window.removeEventListener('keydown', handleKey);
    clearTimeout(progressTimer);
  });

  // ── Navigation ────────────────────────────────────────────────────────────

  function goTo(n) {
    if (!doc) return;
    let p = Math.max(1, Math.min(n, doc.page_count));
    // In double mode always land on an even-numbered page (start of spread),
    // except if we're at page 1 (cover shown alone on the left).
    if (doubleMode && p > 1 && p % 2 !== 0) p = Math.max(1, p - 1);
    if (p === page) return;
    page      = p;
    imgLoaded = false;
    panX      = 0;
    panY      = 0;
    showImages = false;
    location.hash = `#/r/${docId}/${page}`;
    scheduleProgress();
    preload();
  }

  function preload() {
    if (!doc) return;
    const nbs = doubleMode
      ? [page + 2, page + 3, page + 4, page - 2]
      : [page + 1, page + 2, page - 1];
    for (const n of nbs) {
      if (n >= 1 && n <= doc.page_count) new Image().src = pageUrl(n);
    }
  }

  function scheduleProgress() {
    clearTimeout(progressTimer);
    progressTimer = setTimeout(() => updateProgress(docId, page), 300);
  }

  // ── Keyboard ─────────────────────────────────────────────────────────────

  function handleKey(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    switch (e.key) {
      case 'ArrowRight': case 'PageDown': case ' ':
        e.preventDefault(); goTo(page + step); break;
      case 'ArrowLeft': case 'PageUp':
        e.preventDefault(); goTo(page - step); break;
      case 'Home': e.preventDefault(); goTo(1); break;
      case 'End':  e.preventDefault(); goTo(doc?.page_count ?? 1); break;
      case 'f': case 'F': toggleFullscreen(); break;
      case 'g': case 'G': promptGoTo(); break;
      case 't': case 'T': togglePanel('thumbs'); break;
      case 'o': case 'O': togglePanel('toc'); break;
      case 'd': case 'D': toggleDouble(); break;
      case 'b': case 'B': toggleBookmark(); break;
      case '/':  e.preventDefault(); showSearch = !showSearch; break;
      case '+': case '=': zoomBy(1.2); break;
      case '-':  zoomBy(1 / 1.2); break;
      case '0':  resetZoom(); break;
      case 'Escape':
        if      (document.fullscreenElement) document.exitFullscreen();
        else if (showImages)                 showImages = false;
        else if (showSearch)                 showSearch = false;
        else if (panel && panel !== 'thumbs') panel = null;
        break;
    }
  }

  // ── Panel / mode helpers ──────────────────────────────────────────────────

  function togglePanel(name) {
    panel = panel === name ? null : name;
  }

  function toggleDouble() {
    doubleMode = !doubleMode;
    // Snap to start of a spread when entering double mode
    if (doubleMode && page > 1 && page % 2 !== 0) page = Math.max(1, page - 1);
    imgLoaded = false;
    preload();
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  }

  function promptGoTo() {
    const raw = prompt(`Go to page (1–${doc?.page_count}):`);
    const n = parseInt(raw ?? '', 10);
    if (!isNaN(n)) goTo(n);
  }

  // ── Bookmarks ─────────────────────────────────────────────────────────────

  async function toggleBookmark() {
    const existing = bookmarks.find(b => b.page === page);
    if (existing) {
      await apiDeleteBm(existing.id);
      bookmarks = bookmarks.filter(b => b.id !== existing.id);
    } else {
      const bm = await createBookmark(docId, page);
      bookmarks = [...bookmarks, bm];
    }
  }

  async function toggleImages() {
    if (showImages) { showImages = false; return; }
    showImages    = true;
    imagesLoading = true;
    try {
      pageImages = await getPageImages(docId, page);
    } catch (e) {
      pageImages = [];
    } finally {
      imagesLoading = false;
    }
  }

  async function deleteBookmark(id) {
    await apiDeleteBm(id);
    bookmarks = bookmarks.filter(b => b.id !== id);
  }

  // ── Zoom + pan ────────────────────────────────────────────────────────────

  function zoomBy(factor) {
    zoom = Math.max(0.5, Math.min(5.0, zoom * factor));
    if (zoom <= 1.0) { zoom = 1.0; panX = 0; panY = 0; }
  }
  function resetZoom() { zoom = 1.0; panX = 0; panY = 0; }

  function onWheel(e) {
    e.preventDefault();
    zoomBy(e.deltaY < 0 ? 1.1 : 1 / 1.1);
  }

  function onMouseDown(e) {
    if (e.button !== 0) return;
    _drag = false;
    _md   = { x: e.clientX, y: e.clientY, panX, panY };
  }

  function onMouseMove(e) {
    if (!_md) return;
    const dx = e.clientX - _md.x;
    const dy = e.clientY - _md.y;
    if (!_drag && (Math.abs(dx) > 4 || Math.abs(dy) > 4)) _drag = true;
    if (_drag && zoom > 1.0) {
      panX = _md.panX + dx / zoom;
      panY = _md.panY + dy / zoom;
    }
  }

  function onMouseUp() { _md = null; }

  function onAreaClick(e) {
    if (_drag) { _drag = false; return; }  // was a drag, not a tap
    if (zoom > 1.0) return;                // let user pan, not flip page
    const rect = e.currentTarget.getBoundingClientRect();
    const relY = e.clientY - rect.top;
    if (relY < rect.height / 2) {
      goTo(page - step);   // top half → previous page
    } else {
      goTo(page + step);   // bottom half → next page
    }
  }
</script>

{#if loading}
  <div class="loading">Loading…</div>
{:else}
<!-- NOTE: embedded-images modal rendered below the reader block -->
<div class="reader">

  <!-- ── Toolbar ── -->
  <div class="toolbar">
    <a href="#/" class="back">← Library</a>
    <span class="title">{doc.title}</span>

    <div class="nav">
      <button on:click={() => goTo(page - step)} disabled={atFirst} title="Previous (←)">‹</button>
      <button class="page-btn" on:click={promptGoTo} title="Jump to page (G)">
        <span>
          {page}{#if doubleMode && page + 1 <= doc.page_count}–{page + 1}{/if}
        </span>
        <span class="of">/ {doc.page_count}</span>
      </button>
      <button on:click={() => goTo(page + step)} disabled={atLast} title="Next (→)">›</button>
    </div>

    <div class="toolbar-right">
      {#if zoom !== 1.0}
        <button class="icon-btn zoom-chip" on:click={resetZoom} title="Reset zoom (0)">
          {Math.round(zoom * 100)}%
        </button>
      {/if}
      <button
        class="icon-btn"
        class:active={showSearch}
        on:click={() => (showSearch = !showSearch)}
        title="Search (/)">⌕</button>
      <button
        class="icon-btn"
        class:active={isBookmarked}
        on:click={toggleBookmark}
        title="Bookmark this page (B)">{isBookmarked ? '★' : '☆'}</button>
      <button
        class="icon-btn"
        class:active={panel === 'toc'}
        on:click={() => togglePanel('toc')}
        title="Outline + bookmarks (O)">≡</button>
      <button
        class="icon-btn"
        class:active={doubleMode}
        on:click={toggleDouble}
        title="Double-page mode (D)">⊞</button>
      <button
        class="icon-btn"
        class:active={panel === 'thumbs'}
        on:click={() => togglePanel('thumbs')}
        title="Thumbnails (T)">☰</button>
      <button
        class="icon-btn"
        class:active={showImages}
        on:click={toggleImages}
        title="Embedded images">🖼</button>
      <button class="icon-btn" on:click={toggleFullscreen} title="Fullscreen (F)">⛶</button>
    </div>
  </div>

  <!-- ── Main area ── -->
  <div class="body">

    <!-- Page display -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div
      class="page-area"
      class:grab={!_drag && zoom > 1.0}
      class:grabbing={_drag && zoom > 1.0}
      on:wheel|nonpassive={onWheel}
      on:mousedown={onMouseDown}
      on:mousemove={onMouseMove}
      on:mouseup={onMouseUp}
      on:mouseleave={onMouseUp}
      on:click={onAreaClick}
    >
      <div
        class="zoom-wrap"
        style="transform: scale({zoom}) translate({panX}px, {panY}px)"
      >
        {#if doubleMode}
          <!-- Double-page spread: left = page, right = page+1 -->
          <div class="spread">
            <img
              class="spread-img"
              src={pageUrl(page)}
              alt="Page {page}"
              draggable="false"
            />
            {#if page + 1 <= doc.page_count}
              <img
                class="spread-img"
                src={pageUrl(page + 1)}
                alt="Page {page + 1}"
                draggable="false"
              />
            {:else}
              <!-- odd total: show blank right half for last page -->
              <div class="spread-blank"></div>
            {/if}
          </div>
        {:else}
          <!-- Single page with blur-up placeholder -->
          {#if doc.blurhash}
            <img
              class="page-blur"
              class:hidden={imgLoaded}
              src={doc.blurhash}
              alt=""
              aria-hidden="true"
              draggable="false"
            />
          {/if}
          <img
            class="page-img"
            class:visible={imgLoaded}
            src={pageUrl(page)}
            alt="Page {page} of {doc.title}"
            draggable="false"
            on:load={() => (imgLoaded = true)}
          />
        {/if}
      </div>

      <!-- Search overlay (absolute within page-area) -->
      {#if showSearch}
        <SearchPanel
          {doc}
          on:go={(e) => { goTo(e.detail); showSearch = false; }}
          on:close={() => (showSearch = false)}
        />
      {/if}
    </div>

    <!-- Right sidebar: thumbs or TOC+bookmarks -->
    {#if panel === 'thumbs'}
      <ThumbStrip {doc} currentPage={page} on:go={(e) => goTo(e.detail)} />
    {:else if panel === 'toc'}
      <TocPanel
        {outline}
        {bookmarks}
        currentPage={page}
        on:go={(e) => goTo(e.detail)}
        on:close={() => (panel = null)}
        on:delete-bookmark={(e) => deleteBookmark(e.detail)}
      />
    {/if}

  </div>
</div>
{/if}

<!-- ── Embedded images modal ── -->
{#if showImages}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="backdrop" on:click={toggleImages}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="img-modal" on:click|stopPropagation>
      <div class="modal-hd">
        <span>Images — page {page}</span>
        <button on:click={toggleImages}>✕</button>
      </div>
      <div class="modal-bd">
        {#if imagesLoading}
          <p class="hint">Loading…</p>
        {:else if pageImages.length === 0}
          <p class="hint">No embedded images on this page.</p>
        {:else}
          <div class="img-grid">
            {#each pageImages as img}
              <a
                class="img-thumb"
                href="/api/docs/{docId}/page/{page}/images/{img.idx}"
                download="image_p{page}_{img.idx}.{img.ext}"
                title="{img.width}×{img.height} {img.ext.toUpperCase()} — click to download"
              >
                <img
                  src="/api/docs/{docId}/page/{page}/images/{img.idx}"
                  alt="{img.width}×{img.height}"
                />
                <span class="img-dims">{img.width}×{img.height}</span>
              </a>
            {/each}
          </div>
        {/if}
      </div>
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

  .page-btn {
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
    align-items: center;
    gap: 3px;
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
    line-height: 1.3;
    transition: color 80ms, border-color 80ms, background 80ms;
  }
  .icon-btn:hover          { color: #ccc; border-color: #555; }
  .icon-btn.active         { color: #93c5fd; border-color: #3b82f6; background: rgba(59,130,246,.12); }
  .icon-btn.active:hover   { background: rgba(59,130,246,.2); }

  /* Zoom percentage badge in toolbar */
  .zoom-chip {
    font-size: .72rem;
    color: #fbbf24;
    border-color: #92400e;
    min-width: 44px;
    text-align: center;
  }
  .zoom-chip:hover { border-color: #f59e0b; color: #fde68a; }

  /* ── Body ── */
  .body {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  /* ── Page area ── */
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
  .page-area.grab     { cursor: grab; }
  .page-area.grabbing { cursor: grabbing; }

  /* Zoom+pan wrapper — GPU layer */
  .zoom-wrap {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transform-origin: center center;
    will-change: transform;
    pointer-events: none;  /* let right-click reach the <img> directly */
  }

  /* Re-enable pointer events on images so right-click → Save image works;
     left-click still bubbles up to .page-area for navigation/pan. */
  .page-img,
  .spread-img {
    pointer-events: auto;
  }

  /* ── Single-page images ── */
  .page-blur {
    position: absolute;
    max-height: 96%;
    max-width: 96%;
    object-fit: contain;
    filter: blur(20px);
    transform: scale(1.05);
    opacity: 0.4;
    transition: opacity 80ms;
    pointer-events: none;
  }
  .page-blur.hidden { opacity: 0; }

  .page-img {
    position: relative;
    max-height: 96%;
    max-width: 96%;
    object-fit: contain;
    opacity: 0;
    user-select: none;
  }
  .page-img.visible { opacity: 1; }

  /* ── Double-page spread ── */
  .spread {
    display: flex;
    align-items: flex-start;
    gap: 4px;
  }

  .spread-img {
    /* vw/vh-based so sizing is reliable regardless of sidebar state */
    max-height: calc(100vh - 50px);
    max-width: 45vw;
    object-fit: contain;
    display: block;
    flex: 1 1 auto;
    user-select: none;
  }

  .spread-blank {
    flex: 1 1 auto;
    max-width: 45vw;
    background: transparent;
  }

  /* ── Embedded images modal ── */
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
  }
  .img-modal {
    background: #1c1c1c;
    border: 1px solid #2e2e2e;
    border-radius: 10px;
    width: 500px;
    max-width: 90vw;
    max-height: 70vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 16px 48px rgba(0,0,0,.7);
  }
  .modal-hd {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px 10px;
    border-bottom: 1px solid #262626;
    font-size: .82rem;
    color: #aaa;
    flex-shrink: 0;
  }
  .modal-hd button {
    background: none;
    border: none;
    color: #555;
    cursor: pointer;
    font-size: .8rem;
    padding: 2px 6px;
    transition: color 80ms;
  }
  .modal-hd button:hover { color: #ccc; }
  .modal-bd {
    overflow-y: auto;
    padding: 12px;
    flex: 1;
    scrollbar-width: thin;
    scrollbar-color: #333 transparent;
  }
  .hint { color: #555; font-size: .85rem; margin: 4px; }
  .img-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px;
  }
  .img-thumb {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    background: #151515;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 6px;
    text-decoration: none;
    transition: border-color 80ms, background 80ms;
  }
  .img-thumb:hover { border-color: #3b82f6; background: #1a2236; }
  .img-thumb img {
    max-width: 100%;
    max-height: 100px;
    object-fit: contain;
    border-radius: 3px;
    pointer-events: none;
  }
  .img-dims {
    font-size: .6rem;
    color: #555;
    text-align: center;
  }
</style>
