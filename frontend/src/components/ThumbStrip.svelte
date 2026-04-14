<!--
  M2: individual thumb images, loading="lazy" via IntersectionObserver.
  M3 will replace with sprite sheets + virtual scrolling.
-->
<script>
  import { createEventDispatcher, afterUpdate } from 'svelte';
  export let doc;
  export let currentPage;

  const dispatch = createEventDispatcher();
  let container;

  // Keep the active thumb scrolled into view
  afterUpdate(() => {
    if (!container) return;
    const active = container.querySelector('.thumb.active');
    if (active) active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  });

  function padded(n) {
    return String(n).padStart(4, '0');
  }
</script>

<div class="strip" bind:this={container}>
  {#each Array.from({ length: doc.page_count }, (_, i) => i + 1) as p}
    <button
      class="thumb"
      class:active={p === currentPage}
      on:click={() => dispatch('go', p)}
      title="Page {p}"
    >
      <img
        src="/cache/pages/{doc.hash}/thumb/{padded(p)}.webp"
        alt="p.{p}"
        loading="lazy"
        decoding="async"
      />
      <span class="num">{p}</span>
    </button>
  {/each}
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
    gap: 4px;
    padding: 6px 4px;
    scrollbar-width: thin;
    scrollbar-color: #333 transparent;
  }

  .thumb {
    background: none;
    border: 2px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
    overflow: hidden;
    position: relative;
    flex-shrink: 0;
    transition: border-color 80ms;
  }
  .thumb:hover { border-color: #444; }
  .thumb.active { border-color: #3b82f6; }

  .thumb img {
    width: 100%;
    display: block;
    min-height: 40px;
    background: #222;
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
