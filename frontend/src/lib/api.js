const BASE = '/api';

async function _json(url, opts = {}) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

// ── Docs ─────────────────────────────────────────────────────────────────────

export const getDocs = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return _json(`${BASE}/docs${qs ? '?' + qs : ''}`);
};

export const getDoc = (id) => _json(`${BASE}/docs/${id}`);

export const uploadDoc = (file) => {
  const fd = new FormData();
  fd.append('file', file);
  return _json(`${BASE}/docs/upload`, { method: 'POST', body: fd });
};

export const reindexDoc = (id) =>
  _json(`${BASE}/docs/${id}/reindex`, { method: 'POST' });

export const deleteDoc = (id) =>
  fetch(`${BASE}/docs/${id}`, { method: 'DELETE' });

// ── Progress ──────────────────────────────────────────────────────────────────

export const getContinueReading = (limit = 6) =>
  _json(`${BASE}/progress?limit=${limit}`);

export const updateProgress = (id, page) =>
  fetch(`${BASE}/progress/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ page }),
  });

// ── Search ────────────────────────────────────────────────────────────────────

export const search = (q, docId = null, limit = 50) => {
  const p = new URLSearchParams({ q, limit });
  if (docId != null) p.set('doc_id', docId);
  return _json(`${BASE}/search?${p}`);
};

// ── Bookmarks ─────────────────────────────────────────────────────────────────

export const getBookmarks = (docId) =>
  _json(`${BASE}/bookmarks?doc_id=${docId}`);

export const createBookmark = (docId, page, label = null) =>
  _json(`${BASE}/bookmarks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doc_id: docId, page, label }),
  });

export const deleteBookmark = (id) =>
  fetch(`${BASE}/bookmarks/${id}`, { method: 'DELETE' });

// ── Tags ──────────────────────────────────────────────────────────────────────

// ── Page images ───────────────────────────────────────────────────────────────

export const getPageImages = (docId, pageNum) =>
  _json(`${BASE}/docs/${docId}/page/${pageNum}/images`);

// ── Tags ──────────────────────────────────────────────────────────────────────

export const getTags = () => _json(`${BASE}/tags`);

export const createTag = (name) =>
  _json(`${BASE}/tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });

export const deleteTag = (id) =>
  fetch(`${BASE}/tags/${id}`, { method: 'DELETE' });

export const addDocTag = (docId, tagId) =>
  fetch(`${BASE}/docs/${docId}/tags/${tagId}`, { method: 'POST' });

export const removeDocTag = (docId, tagId) =>
  fetch(`${BASE}/docs/${docId}/tags/${tagId}`, { method: 'DELETE' });
