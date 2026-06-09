<script>
  import { onMount } from 'svelte';
  import Gallery from './views/Gallery.svelte';
  import Reader from './views/Reader.svelte';
  import TagsPage from './views/TagsPage.svelte';

  let route = { name: 'gallery' };

  function parseRoute() {
    const h = (location.hash || '#/').slice(1);
    if (h === '/tags') {
      route = { name: 'tags' };
      return;
    }
    const m = h.match(/^\/r\/(\d+)(?:\/(\d+))?$/);
    if (m) {
      route = { name: 'reader', id: +m[1], page: +(m[2] || 1) };
    } else {
      route = { name: 'gallery' };
    }
  }

  onMount(() => {
    parseRoute();
    window.addEventListener('hashchange', parseRoute);
    return () => window.removeEventListener('hashchange', parseRoute);
  });
</script>

{#if route.name === 'gallery'}
  <Gallery />
{:else if route.name === 'reader'}
  <Reader docId={route.id} initialPage={route.page} />
{:else if route.name === 'tags'}
  <TagsPage />
{/if}
