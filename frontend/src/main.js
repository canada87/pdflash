import App from './App.svelte';

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(console.error);
}

const app = new App({ target: document.body });
export default app;
