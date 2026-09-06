/* Progressive enhancements. Navigation and the complete gallery work without JS. */
(() => {
  document.documentElement.classList.remove('no-js');
  const menu = document.querySelector('.menu-toggle');
  const sidebar = document.querySelector('#sidebar');
  const closeMenu = () => {
    if (sidebar.classList.contains('is-open') && sidebar.contains(document.activeElement)) menu.focus();
    sidebar.classList.remove('is-open'); menu.setAttribute('aria-expanded', 'false');
  };
  menu.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(open)); sidebar.classList.toggle('is-open', open);
  });
  document.addEventListener('click', event => {
    if (!sidebar.contains(event.target) && !menu.contains(event.target)) closeMenu();
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
  matchMedia('(min-width: 761px)').addEventListener('change', closeMenu);

  async function copy(button, value) {
    const label = button.textContent;
    try {
      await navigator.clipboard.writeText(value);
      button.textContent = 'Copied';
    } catch (_) { button.textContent = 'Select to copy'; }
    setTimeout(() => { button.textContent = label; }, 1800);
  }
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', () => copy(button, button.dataset.copy)));
  document.querySelectorAll('.prose img').forEach(image => {
    if (image.closest('a')) return;
    const link = document.createElement('a');
    link.href = image.src; link.className = 'figure-zoom';
    link.setAttribute('aria-label', 'Open full-size figure: ' + image.alt);
    image.replaceWith(link); link.append(image);
  });
  document.querySelectorAll('.codehilite').forEach(block => {
    const code = block.querySelector('code') || block.querySelector('pre');
    if (!code) return;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'copy-code'; button.textContent = 'Copy';
    button.setAttribute('aria-label', 'Copy code'); button.addEventListener('click', () => copy(button, code.textContent));
    block.append(button);
  });

  const toolbar = document.querySelector('.gallery-toolbar');
  if (toolbar) {
    toolbar.hidden = false;
    const cards = [...document.querySelectorAll('.gallery-grid .gallery-card')];
    const filters = [...toolbar.querySelectorAll('[data-filter]')];
    const query = document.querySelector('#gallery-query');
    const params = new URLSearchParams(location.search);
    let category = filters.some(b => b.dataset.filter === params.get('type')) ? params.get('type') : 'all';
    query.value = params.get('q') || '';
    function filter() {
      const terms = query.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
      let count = 0;
      cards.forEach(card => {
        card.hidden = (category !== 'all' && card.dataset.category !== category) || !terms.every(term => card.dataset.title.toLowerCase().includes(term));
        if (!card.hidden) count++;
      });
      filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === category)));
      document.querySelector('.gallery-count').textContent = `${count} ${count === 1 ? 'example' : 'examples'} · select a figure for source and instructions`;
      document.querySelector('.gallery-empty').hidden = count > 0;
      const url = new URL(location.href);
      category === 'all' ? url.searchParams.delete('type') : url.searchParams.set('type', category);
      query.value ? url.searchParams.set('q', query.value) : url.searchParams.delete('q');
      history.replaceState(null, '', url);
    }
    filters.forEach(button => button.addEventListener('click', () => { category = button.dataset.filter; filter(); }));
    query.addEventListener('input', filter); filter();
  }

  const dialog = document.querySelector('.search-dialog');
  const input = document.querySelector('#docs-search');
  const status = document.querySelector('.search-status');
  const results = document.querySelector('.search-results');
  const root = new URL(document.body.dataset.siteRoot.replace(/\/?$/, '/'), location.href);
  let indexPromise, timer, sequence = 0;
  function loadIndex() {
    if (!indexPromise) indexPromise = fetch(document.body.dataset.searchIndex).then(response => {
      if (!response.ok) throw new Error('Search index unavailable');
      return response.json();
    }).then(data => data.docs.map(doc => ({...doc, titleLower: doc.title.toLowerCase(), textLower: doc.text.toLowerCase()}))).catch(error => { indexPromise = null; throw error; });
    return indexPromise;
  }
  async function search() {
    const current = ++sequence;
    const terms = input.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    results.replaceChildren();
    if (!terms.length) { status.textContent = 'Type to search guides, examples and the API.'; return; }
    status.textContent = 'Searching…';
    try {
      const index = await loadIndex();
      if (current !== sequence) return;
      const matches = index.filter(doc => terms.every(term => doc.titleLower.includes(term) || doc.textLower.includes(term)))
        .map(doc => ({doc, score: terms.reduce((sum, term) => sum + (doc.titleLower.includes(term) ? 10 : 0), 0)}))
        .sort((a, b) => b.score - a.score).slice(0, 12);
      status.textContent = matches.length ? `Showing ${matches.length} matching sections` : 'No results. Try a shorter term or a different spelling.';
      matches.forEach(({doc}) => {
        const url = new URL(doc.location, root);
        if (url.origin !== location.origin || !url.pathname.startsWith(root.pathname)) return;
        const link = document.createElement('a'); link.href = url.href;
        const title = document.createElement('strong');
        const signature = doc.title.indexOf('(');
        title.textContent = doc.title.length <= 110 ? doc.title
          : signature > 0 ? doc.title.slice(0, signature) + '(…)'
          : doc.title.slice(0, 107) + '…';
        link.title = doc.title;
        const text = document.createElement('span');
        const position = Math.max(0, doc.textLower.indexOf(terms[0]) - 45);
        text.textContent = (position ? '…' : '') + doc.text.slice(position, position + 170) + (doc.text.length > position + 170 ? '…' : '');
        link.append(title, text); results.append(link);
      });
    } catch (_) {
      if (current === sequence) status.textContent = 'Search could not load. Check your connection and try typing again.';
    }
  }
  function openSearch() { if (!dialog.open) dialog.showModal(); input.focus(); search(); }
  document.querySelector('[data-search-open]').addEventListener('click', openSearch);
  document.querySelector('[data-search-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog && (event.clientX < dialog.getBoundingClientRect().left || event.clientX > dialog.getBoundingClientRect().right || event.clientY < dialog.getBoundingClientRect().top || event.clientY > dialog.getBoundingClientRect().bottom)) dialog.close(); });
  input.addEventListener('input', () => { ++sequence; clearTimeout(timer); timer = setTimeout(search, 120); });
  document.addEventListener('keydown', event => {
    const typing = event.target.closest('input, textarea, [contenteditable="true"]');
    if ((event.key === '/' && !typing) || ((event.ctrlKey || event.metaKey) && event.key === 'k')) { event.preventDefault(); openSearch(); }
  });
  const headings = [...document.querySelectorAll('.prose h2[id]')];
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      document.querySelectorAll('.page-toc a').forEach(link => link.classList.toggle('active', link.hash === '#' + entry.target.id));
    }), {rootMargin: '-90px 0px -65% 0px'});
    headings.forEach(heading => observer.observe(heading));
  }
})();
