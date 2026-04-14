<!--
  M3: sprite sheets + virtual scroll.
  - Fetches manifest.json once; fires ≤ ceil(pages/50) HTTP requests for sheet WebPs.
  - Only renders DOM nodes for the visible window + BUFFER items above/below viewport.
  - Service Worker caches all /cache/* assets after first visit → 0 ms on second visit.
-->
<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';

  export let doc;
  export let currentPage;

  const dispatch = createEventDispatcher();

  // Strip inner content width  (116px container − 2×4px horizontal padding)
  const STRIP_W = 108;
  // Gap between items (margin-bottom on each .thumb)
  const GAP = 4;
  // ITEM_H is always STRIP_W + GAP because the sprite cell is scaled to STRIP_W × STRIP_W
  const ITEM_H = STRIP_W + GAP;   // 112 px
  // Extra items rendered above/below the visible viewport
  const BUFFER = 5;

  let manifest = null;
  let scale     = 1;
  let container;
  let scrollTop  = 0;
  let containerH = 600;

  // ── Lifecycle ────────────────────────────────────────────────────────────────

  onMount(async () => {
    containerH = container?.clientHeight ?? 600;
    window.addEventListener('resize', onResize);

    const res = await fetch(`/cache/pages/${doc.hash}/sprites/manifest.json`);
    if (!res.ok) return;
    const m = await res.json();
    scale    = STRIP_W / m.cell_px;   // uniform scale: cell fits into STRIP_W square
    manifest = m;
    // Scroll to the already-active page without animation on first load
    const target = (currentPage - 1) * ITEM_H - (containerH - ITEM_H) / 2;
    container?.scrollTo({ top: Math.max(0, target), behavior: 'auto' });
  });

  onDestroy(() => window.removeEventListener('resize', onResize));

  function onResize() {
    containerH = container?.clientHeight ?? containerH;
  }

  // ── Scroll handling ───────────────────────────────────────────────────────────

  function onScroll() {
    scrollTop = container.scrollTop;
  }

  // Scroll the active page into view whenever currentPage changes (or manifest loads).
  // Reads container.scrollTop directly — not the reactive `scrollTop` — so this
  // statement does NOT re-fire on every scroll event.
  $: if (manifest && container) _ensureVisible(currentPage);

  function _ensureVisible(p) {
    const top = (p - 1) * ITEM_H;
    const bot = top + ITEM_H;
    const st  = container.scrollTop;
    if (top < st + 2 || bot > st + containerH - 2) {
      container.scrollTo({
        top: Math.max(0, top - (containerH - ITEM_H) / 2),
        behavior: 'smooth',
      });
    }
  }

  // ── Virtual scroll ────────────────────────────────────────────────────────────

  $: startIdx = Math.max(0, Math.floor(scrollTop / ITEM_H) - BUFFER);
  $: endIdx   = manifest
    ? Math.min(doc.page_count - 1, Math.ceil((scrollTop + containerH) / ITEM_H) - 1 + BUFFER)
    : -1;

  // Spacer heights to maintain correct total scroll height
  $: topSpace = startIdx * ITEM_H;
  $: botSpace = Math.max(0, (doc.page_count - 1 - endIdx) * ITEM_H);

  // ── Sprite CSS ────────────────────────────────────────────────────────────────

  function thumbStyle(p) {
    const info  = manifest.pages[String(p)];
    if (!info) return '';
    const sheet = manifest.sheets[info.s];
    // Scale the whole sprite sheet down so the cell fits into STRIP_W × STRIP_W.
    return [
      `background-image:url(/cache/pages/${doc.hash}/sprites/${sheet.file})`,
      `background-position:-${(info.x * scale).toFixed(1)}px -${(info.y * scale).toFixed(1)}px`,
      `background-size:${(sheet.w * scale).toFixed(1)}px ${(sheet.h * scale).toFixed(1)}px`,
    ].join(';');
  }
</script>

<div class="strip" bind:this={container} on:scroll={onScroll}>
  {#if !manifest}
    <!-- Skeleton placeholders while manifest loads -->
    {#each Array(10) as _}
      <div class="skel"></div>
    {/each}
  {:else}
    <div style="height:{topSpace}px;flex-shrink:0"></div>

    {#each Array.from({ length: endIdx - startIdx + 1 }, (_, i) => startIdx + i + 1) as p}
      <button
        class="thumb"
        class:active={p === currentPage}
        on:click={() => dispatch('go', p)}
        title="Page {p}"
      >
        <!--
          .sprite-cell is exactly STRIP_W × STRIP_W px (a square matching the sprite cell).
          The PDF page thumbnail is centred within this square by the sprite builder.
          box-shadow:inset is used for the active/hover ring so it has zero layout impact.
        -->
        <div class="sprite-cell" style={thumbStyle(p)}></div>
        <span class="num">{p}</span>
      </button>
    {/each}

    <div style="height:{botSpace}px;flex-shrink:0"></div>
  {/if}
</div>

<style>
  .strip {
    width: 116px;
    flex: 0 0 116px;
    overflow-y: auto;
    overflow-x: hidden;
    background: #161616;
    border-left: 1px solid #262626;
    display: flex;
    flex-direction: column;
    padding: 6px 4px;
    scrollbar-width: thin;
    scrollbar-color: #333 transparent;
  }

  /* Loading skeleton */
  .skel {
    width: 108px;
    height: 108px;
    margin-bottom: 4px;
    border-radius: 4px;
    background: #222;
    flex-shrink: 0;
    animation: pulse 1.4s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: .4; }
    50%       { opacity: .7; }
  }

  .thumb {
    background: none;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
    overflow: hidden;
    position: relative;
    flex-shrink: 0;
    margin-bottom: 4px;    /* = GAP; makes outer height = STRIP_W + GAP = ITEM_H = 112px */
    width: 108px;          /* = STRIP_W */
    /* Inset ring has zero layout impact — does not affect height calculation */
    box-shadow: inset 0 0 0 2px transparent;
    transition: box-shadow 80ms;
  }
  .thumb:hover  { box-shadow: inset 0 0 0 2px #444; }
  .thumb.active { box-shadow: inset 0 0 0 2px #3b82f6; }

  /* Square cell matching the sprite grid cell (scaled to STRIP_W × STRIP_W) */
  .sprite-cell {
    display: block;
    width: 108px;
    height: 108px;
    background-repeat: no-repeat;
    background-color: #222;
  }

  .num {
    position: absolute;
    bottom: 2px;
    right: 4px;
    font-size: .6rem;
    color: #fff;
    text-shadow: 0 0 4px #000;
    pointer-events: none;
  }
</style>
