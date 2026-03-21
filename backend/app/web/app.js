const DB_NAME = 'reader-system-db';
const DB_VERSION = 1;
const TOKEN_KEY = 'readerToken';

const state = {
  token: localStorage.getItem(TOKEN_KEY),
  currentBookId: null,
  currentChapterId: null,
  chapters: [],
};

async function openDb() {
  return await new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains('books')) db.createObjectStore('books', { keyPath: 'id' });
      if (!db.objectStoreNames.contains('chapters')) db.createObjectStore('chapters', { keyPath: 'key' });
      if (!db.objectStoreNames.contains('progress')) db.createObjectStore('progress', { keyPath: 'book_id' });
      if (!db.objectStoreNames.contains('pending_sync')) db.createObjectStore('pending_sync', { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbPut(storeName, value) {
  const db = await openDb();
  return await new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).put(value);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function idbGet(storeName, key) {
  const db = await openDb();
  return await new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).get(key);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

async function idbGetAll(storeName) {
  const db = await openDb();
  return await new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

async function idbDelete(storeName, key) {
  const db = await openDb();
  return await new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    tx.objectStore(storeName).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

function setStatus(text) {
  document.getElementById('sync-status').textContent = text;
}

function authHeaders() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

async function authMagic() {
  const email = document.getElementById('email').value.trim();
  if (!email) return;
  await fetch('/api/v1/auth/magic/request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  alert('Magic link sent (or simulated if SMTP disabled).');
}

async function applyTokenFromUrl() {
  const token = new URLSearchParams(window.location.search).get('token');
  if (!token) return;
  const resp = await fetch('/api/v1/auth/magic/consume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!resp.ok) return;
  const data = await resp.json();
  state.token = data.access_token;
  localStorage.setItem(TOKEN_KEY, state.token);
  history.replaceState({}, '', '/app');
}

async function fetchLibrary() {
  let resp = await fetch('/api/v1/library?page=1&page_size=50', { headers: authHeaders() });
  if (!resp.ok) {
    const offlineBooks = await idbGetAll('books');
    renderLibrary(offlineBooks.map((b) => ({ ...b, status: b.status || 'cached' })));
    setStatus('Offline library from IndexedDB');
    return;
  }
  const data = await resp.json();
  for (const book of data.items) await idbPut('books', book);
  renderLibrary(data.items);
}

function renderLibrary(items) {
  const container = document.getElementById('library-list');
  container.innerHTML = '';
  items.forEach((book) => {
    const row = document.createElement('div');
    row.className = 'book-row';
    row.innerHTML = `<button data-id="${book.id}">${book.title}</button><span>${book.author}</span><span>${book.status}</span>`;
    row.querySelector('button').addEventListener('click', () => openBook(book.id));
    container.appendChild(row);
  });
}

async function openBook(bookId) {
  state.currentBookId = bookId;
  localStorage.setItem('lastBookId', bookId);
  setStatus('Loading chapters...');
  let chapters = [];
  const online = navigator.onLine;
  if (online) {
    const resp = await fetch(`/api/v1/books/${bookId}/chapters`, { headers: authHeaders() });
    if (resp.ok) {
      chapters = await resp.json();
      await idbPut('books', { ...(await idbGet('books', bookId)), id: bookId, chapters_indexed: true });
      for (const chapter of chapters) {
        const cResp = await fetch(`/api/v1/books/${bookId}/chapter/${chapter.id}`, { headers: authHeaders() });
        if (cResp.ok) {
          const detail = await cResp.json();
          await idbPut('chapters', { key: `${bookId}:${chapter.id}`, value: detail });
        }
      }
    }
  }

  if (chapters.length === 0) {
    const cached = await idbGetAll('chapters');
    const filtered = cached.filter((x) => x.key.startsWith(`${bookId}:`)).map((x) => x.value);
    chapters = filtered.map((f) => ({ id: f.id, title: f.title, order_index: f.order_index, chapter_type: f.chapter_type }));
  }

  state.chapters = chapters.sort((a, b) => a.order_index - b.order_index);
  if (!state.chapters.length) {
    setStatus('No chapters found');
    return;
  }

  const saved = await idbGet('progress', bookId);
  const startChapter = saved?.chapter_id || state.chapters[0].id;
  await openChapter(startChapter);
  setStatus('Ready');
}

async function openChapter(chapterId) {
  state.currentChapterId = chapterId;
  localStorage.setItem('lastChapterId', String(chapterId));
  const key = `${state.currentBookId}:${chapterId}`;
  let chapter = await idbGet('chapters', key);
  if (!chapter && navigator.onLine) {
    const resp = await fetch(`/api/v1/books/${state.currentBookId}/chapter/${chapterId}`, { headers: authHeaders() });
    if (resp.ok) {
      chapter = await resp.json();
      await idbPut('chapters', { key, value: chapter });
    }
  }
  if (!chapter) {
    setStatus('Chapter unavailable offline');
    return;
  }

  const content = document.getElementById('reader-content');
  content.innerHTML = chapter.content;

  const progress = await idbGet('progress', state.currentBookId);
  if (progress && progress.chapter_id === chapterId && progress.position > 0) {
    content.scrollTop = progress.position;
  }

  preloadNeighbors(chapter.prev_chapter_id, chapter.next_chapter_id);
}

async function preloadNeighbors(prevId, nextId) {
  for (const id of [prevId, nextId]) {
    if (!id || !navigator.onLine) continue;
    const key = `${state.currentBookId}:${id}`;
    const exists = await idbGet('chapters', key);
    if (exists) continue;
    const resp = await fetch(`/api/v1/books/${state.currentBookId}/chapter/${id}`, { headers: authHeaders() });
    if (resp.ok) await idbPut('chapters', { key, value: await resp.json() });
  }
}

async function saveProgress() {
  if (!state.currentBookId || !state.currentChapterId) return;
  const position = document.getElementById('reader-content').scrollTop;
  const payload = {
    book_id: state.currentBookId,
    chapter_id: state.currentChapterId,
    position,
    updated_at: new Date().toISOString(),
  };
  await idbPut('progress', payload);
  await idbPut('pending_sync', payload);
  await flushProgressQueue();
}

async function flushProgressQueue() {
  if (!navigator.onLine || !state.token) return;
  const pending = await idbGetAll('pending_sync');
  if (!pending.length) return;

  setStatus(`Syncing ${pending.length} updates...`);
  for (const item of pending) {
    const resp = await fetch('/api/v1/progress', {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(item),
    });
    if (!resp.ok) continue;
    const result = await resp.json();
    if (!result.accepted && result.server_progress) {
      await idbPut('progress', {
        book_id: result.server_progress.book_id,
        chapter_id: result.server_progress.chapter_id,
        position: result.server_progress.position,
        updated_at: result.server_progress.updated_at,
      });
    }
    if (item.id) await idbDelete('pending_sync', item.id);
  }
  setStatus('Synced');
}

function bindControls() {
  document.getElementById('send-magic').addEventListener('click', authMagic);
  document.getElementById('reader-content').addEventListener('scroll', () => {
    window.clearTimeout(window.__saveTimer);
    window.__saveTimer = setTimeout(saveProgress, 300);
  });

  document.getElementById('prev').addEventListener('click', async () => {
    const cur = state.chapters.find((x) => x.id === state.currentChapterId);
    const prev = state.chapters.find((x) => x.order_index === cur.order_index - 1);
    if (prev) await openChapter(prev.id);
  });

  document.getElementById('next').addEventListener('click', async () => {
    const cur = state.chapters.find((x) => x.id === state.currentChapterId);
    const next = state.chapters.find((x) => x.order_index === cur.order_index + 1);
    if (next) await openChapter(next.id);
  });

  window.addEventListener('online', flushProgressQueue);
}

async function init() {
  if ('serviceWorker' in navigator) {
    await navigator.serviceWorker.register('/sw.js');
  }
  await applyTokenFromUrl();
  bindControls();
  if (state.token) {
    await fetchLibrary();
    const lastBook = localStorage.getItem('lastBookId');
    if (lastBook) await openBook(lastBook);
  }
}

init();
