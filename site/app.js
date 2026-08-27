/* The review app. One static origin, one fetch, no framework.
 *
 * THE CLIPBOARD RULE, which is the only subtle thing in this file:
 *
 *   iOS Safari honours navigator.clipboard.writeText only when it is called
 *   synchronously inside the tap handler. Any await before the call - a fetch,
 *   a JSON parse, a promise chain - and Safari silently refuses. Nothing
 *   throws. Nothing is copied. So the caption is loaded with index.json at
 *   startup, held on the button as a plain string, and written on tap with no
 *   intervening statement that yields.
 */

const state = { posts: [], current: null, slide: 0 };

async function boot() {
  let data;
  try {
    const res = await fetch('index.json', { cache: 'no-store' });
    data = await res.json();
  } catch (err) {
    document.getElementById('empty').hidden = false;
    return;
  }
  state.posts = data.posts || [];
  if (!state.posts.length) document.getElementById('empty').hidden = false;
  renderLists();
  wireTabs();
}

function renderLists() {
  const ready = state.posts.filter(p => p.status === 'ready');
  const posted = state.posts.filter(p => p.status === 'posted');
  const draft = state.posts.filter(p => p.status === 'draft');

  const today = ready[0] || draft[0] || posted[0];
  document.getElementById('today').innerHTML = today
    ? card(today, true)
    : '<p class="none">nothing waiting.</p>';

  document.getElementById('ready').innerHTML =
    ready.length ? ready.map(p => card(p)).join('') : '<p class="none">none ready.</p>';
  document.getElementById('archive').innerHTML =
    posted.length ? posted.map(p => card(p)).join('') : '<p class="none">nothing posted yet.</p>';

  document.querySelectorAll('[data-post]').forEach(el => {
    el.addEventListener('click', () => openPost(el.dataset.post));
  });
}

function card(post, big) {
  return `
    <article class="card ${big ? 'big' : ''} ${post.mourning ? 'mourning' : ''}">
      <h3>${escapeHtml(post.title)}</h3>
      <p class="meta">${post.pillar} · ${post.slide_count} slides · ${post.status}</p>
      <button class="button" data-post="${post.id}">review</button>
    </article>`;
}

function openPost(id) {
  const post = state.posts.find(p => p.id === id);
  if (!post) return;
  state.current = post;
  state.slide = 0;

  document.getElementById('post-title').textContent = post.title;
  document.getElementById('post-meta').textContent =
    `${post.running_head} · ${post.pillar} · ${post.slide_count} slides`;
  document.getElementById('track').innerHTML = post.slides
    .map(s => `<img src="${s.png}" alt="slide ${s.position}" loading="lazy">`)
    .join('');
  document.getElementById('download').href = post.zip;
  document.getElementById('caption').textContent = post.caption;

  // The caption is on the button BEFORE any tap can happen.
  const copy = document.getElementById('copy');
  copy.dataset.caption = post.caption;
  copy.textContent = 'copy caption';

  show('post');
  updateCounter();
}

function updateCounter() {
  const post = state.current;
  if (!post) return;
  document.getElementById('counter').textContent =
    `${state.slide + 1} / ${post.slides.length}`;
}

function wireTabs() {
  document.querySelectorAll('#tabs button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#tabs button').forEach(b => b.classList.remove('on'));
      btn.classList.add('on');
      show(btn.dataset.screen);
    });
  });

  document.getElementById('back').addEventListener('click', () => {
    show(document.querySelector('#tabs button.on').dataset.screen);
  });

  const track = document.getElementById('track');
  track.addEventListener('scroll', () => {
    const index = Math.round(track.scrollLeft / track.clientWidth);
    if (index !== state.slide) { state.slide = index; updateCounter(); }
  }, { passive: true });

  // No await, no fetch, no promise before writeText. This is the whole trick.
  document.getElementById('copy').addEventListener('click', function () {
    const text = this.dataset.caption || '';
    const button = this;
    try {
      navigator.clipboard.writeText(text).then(
        () => { button.textContent = 'copied'; },
        () => { button.textContent = 'press and hold the caption'; }
      );
    } catch (err) {
      button.textContent = 'press and hold the caption';
    }
    setTimeout(() => { button.textContent = 'copy caption'; }, 2200);
  });
}

function show(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('on'));
  document.getElementById(id).classList.add('on');
  window.scrollTo(0, 0);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

boot();
