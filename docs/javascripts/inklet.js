/* Progressive enhancements. Navigation, figures and the complete gallery work without JS. */
(() => {
  const root = document.documentElement;
  root.classList.remove('no-js');
  root.classList.add('js-ready');

  /* ---- Colour theme ---- */
  const themeButton = document.querySelector('.theme-toggle');
  const darkQuery = matchMedia('(prefers-color-scheme: dark)');
  const currentTheme = () => root.getAttribute('data-theme') || (darkQuery.matches ? 'dark' : 'light');
  const labelTheme = () => {
    if (themeButton) themeButton.setAttribute('aria-label', currentTheme() === 'dark' ? 'Use light theme' : 'Use dark theme');
  };
  if (themeButton) {
    themeButton.addEventListener('click', () => {
      const next = currentTheme() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('inklet-theme', next); } catch (_) { /* storage unavailable */ }
      labelTheme();
    });
    darkQuery.addEventListener('change', labelTheme);
    labelTheme();
  }

  /* ---- Navigation drawer ---- */
  const menu = document.querySelector('.menu-toggle');
  const sidebar = document.querySelector('#sidebar');
  const backdrop = document.querySelector('.nav-backdrop');
  const drawerMode = () => getComputedStyle(menu).display !== 'none';
  function setMenu(open, restoreFocus = true) {
    if (!menu || !sidebar) return;
    const wasOpen = sidebar.classList.contains('is-open');
    sidebar.classList.toggle('is-open', open);
    menu.setAttribute('aria-expanded', String(open));
    menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    if (backdrop) backdrop.hidden = !open;
    document.body.style.overflow = open ? 'hidden' : '';
    if (open) {
      const current = sidebar.querySelector('[aria-current="page"]') || sidebar.querySelector('a, summary');
      if (current) { current.scrollIntoView({block: 'center'}); current.focus({preventScroll: true}); }
    } else if (wasOpen && restoreFocus && sidebar.contains(document.activeElement)) menu.focus();
  }
  if (menu && sidebar) {
    menu.addEventListener('click', () => setMenu(menu.getAttribute('aria-expanded') !== 'true'));
    if (backdrop) backdrop.addEventListener('click', () => setMenu(false));
    sidebar.addEventListener('click', event => { if (event.target.closest('a') && drawerMode()) setMenu(false, false); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && sidebar.classList.contains('is-open')) setMenu(false); });
    matchMedia('(min-width: 1024px)').addEventListener('change', () => setMenu(false, false));
    // Keep the current page visible in a long sidebar.
    const current = sidebar.querySelector('[aria-current="page"]');
    if (current && !drawerMode()) {
      const box = sidebar.getBoundingClientRect(), item = current.getBoundingClientRect();
      if (item.bottom > box.bottom - 40) sidebar.scrollTop += item.top - box.top - box.height / 3;
    }
  }

  /* ---- Copy buttons ---- */
  const copyIcon = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 3.5v-.5A1.5 1.5 0 0 0 9 1.5H3A1.5 1.5 0 0 0 1.5 3v6A1.5 1.5 0 0 0 3 10.5h.5"/></svg>';
  async function copy(button, value, label) {
    try {
      await navigator.clipboard.writeText(value);
      button.classList.add('done'); label.textContent = 'Copied';
    } catch (_) { label.textContent = 'Select to copy'; }
    clearTimeout(button.copyTimer);
    button.copyTimer = setTimeout(() => { button.classList.remove('done'); label.textContent = 'Copy'; }, 1600);
  }
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', () => copy(button, button.dataset.copy, button)));
  document.querySelectorAll('.codehilite').forEach(block => {
    const code = block.querySelector('code') || block.querySelector('pre');
    if (!code) return;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'copy-code';
    button.innerHTML = copyIcon + '<span>Copy</span>';
    button.setAttribute('aria-label', 'Copy code');
    const label = button.querySelector('span');
    button.addEventListener('click', () => copy(button, code.textContent.replace(/\n$/, ''), label));
    block.append(button);
  });

  /* ---- Lightbox ---- */
  const lightbox = document.querySelector('.lightbox');
  function openLightbox(src, title, href) {
    if (!lightbox || typeof lightbox.showModal !== 'function') return false;
    const image = lightbox.querySelector('img');
    image.src = src; image.alt = title || '';
    lightbox.querySelector('.lightbox-title').textContent = title || '';
    const open = lightbox.querySelector('.lightbox-open');
    open.hidden = !href; if (href) open.href = href;
    lightbox.querySelector('.lightbox-full').href = src;
    lightbox.showModal();
    lightbox.querySelector('.lightbox-close').focus();
    return true;
  }
  if (lightbox) {
    lightbox.querySelector('.lightbox-close').addEventListener('click', () => lightbox.close());
    lightbox.addEventListener('click', event => { if (event.target === lightbox || event.target.classList.contains('lightbox-sheet')) lightbox.close(); });
    lightbox.addEventListener('close', () => { lightbox.querySelector('img').removeAttribute('src'); });
  }
  const plain = event => !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button > 0);
  document.querySelectorAll('.prose img').forEach(image => {
    if (image.closest('a') || image.closest('.brand-preview, .brand-sizes')) return;
    const link = document.createElement('a');
    link.href = image.currentSrc || image.src; link.className = 'figure-zoom';
    link.setAttribute('aria-label', 'Enlarge figure: ' + (image.alt || 'figure'));
    image.replaceWith(link); link.append(image);
    link.addEventListener('click', event => {
      if (plain(event) && openLightbox(link.href, image.alt)) event.preventDefault();
    });
  });
  document.querySelectorAll('[data-lightbox]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => openLightbox(button.dataset.lightbox, button.dataset.lightboxTitle, button.dataset.lightboxHref));
  });

  /* ---- Gallery filters ---- */
  const toolbar = document.querySelector('.gallery-toolbar');
  if (toolbar) {
    toolbar.hidden = false;
    const cards = [...document.querySelectorAll('.gallery-grid .gallery-card')];
    const filters = [...toolbar.querySelectorAll('[data-filter]')];
    const query = document.querySelector('#gallery-query');
    const reset = toolbar.querySelector('.gallery-reset');
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
      // The plot gallery groups cards by family; hide a family with no matches.
      document.querySelectorAll('.gallery-group').forEach(group => {
        group.hidden = !group.querySelector('.gallery-card:not([hidden])');
      });
      filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === category)));
      document.querySelector('.gallery-count').textContent = `${count} ${count === 1 ? 'example' : 'examples'}`;
      document.querySelector('.gallery-empty').hidden = count > 0;
      if (reset) reset.hidden = category === 'all' && !query.value;
      const url = new URL(location.href);
      category === 'all' ? url.searchParams.delete('type') : url.searchParams.set('type', category);
      query.value ? url.searchParams.set('q', query.value) : url.searchParams.delete('q');
      history.replaceState(null, '', url);
    }
    filters.forEach(button => button.addEventListener('click', () => { category = button.dataset.filter; filter(); }));
    if (reset) reset.addEventListener('click', () => { category = 'all'; query.value = ''; filter(); query.focus(); });
    query.addEventListener('input', filter); filter();
  }

  /* ---- Search ---- */
  const dialog = document.querySelector('.search-dialog');
  const input = document.querySelector('#docs-search');
  const section = document.querySelector('#search-section');
  const status = document.querySelector('.search-status');
  const results = document.querySelector('.search-results');
  const siteRoot = new URL(document.body.dataset.siteRoot.replace(/\/?$/, '/'), location.href);
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
      const seenPages = new Set();
      const matches = index.filter(doc => (!section.value || doc.section === section.value) && terms.every(term => doc.titleLower.includes(term) || doc.textLower.includes(term)))
        .map(doc => ({doc, score: terms.reduce((sum, term) => sum + (doc.titleLower.includes(term) ? 10 : 0), 0)}))
        .sort((a, b) => b.score - a.score)
        .filter(({doc}) => {
          const page = doc.location.split('#')[0];
          if (seenPages.has(page)) return false;
          seenPages.add(page); return true;
        }).slice(0, 12);
      status.textContent = matches.length ? `${matches.length} matching ${matches.length === 1 ? 'page' : 'pages'}` : 'No results. Try a shorter term or a different spelling.';
      matches.forEach(({doc}) => {
        const url = new URL(doc.location, siteRoot);
        if (url.origin !== location.origin || !url.pathname.startsWith(siteRoot.pathname)) return;
        url.searchParams.set('v', document.body.dataset.pageVersion);
        const link = document.createElement('a'); link.href = url.href;
        const context = document.createElement('small');
        context.textContent = [doc.section, doc.page_title].filter(Boolean).join(' / ');
        const title = document.createElement('strong');
        const signature = doc.title.indexOf('(');
        title.textContent = doc.title.length <= 110 ? doc.title
          : signature > 0 ? doc.title.slice(0, signature) + '(…)'
          : doc.title.slice(0, 107) + '…';
        link.title = doc.title;
        const text = document.createElement('span');
        const position = Math.max(0, doc.textLower.indexOf(terms[0]) - 45);
        text.textContent = (position ? '…' : '') + doc.text.slice(position, position + 170) + (doc.text.length > position + 170 ? '…' : '');
        link.append(context, title, text); results.append(link);
      });
    } catch (_) {
      if (current === sequence) status.textContent = 'Search could not load. Check your connection and try typing again.';
    }
  }
  function openSearch() { if (!dialog.open) dialog.showModal(); input.focus(); input.select(); search(); }
  document.querySelectorAll('[data-search-open]').forEach(button => button.addEventListener('click', openSearch));
  document.querySelector('[data-search-close]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  input.addEventListener('input', () => { ++sequence; clearTimeout(timer); timer = setTimeout(search, 120); });
  input.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown' || event.key === 'Enter') {
      const first = results.querySelector('a');
      if (!first) return;
      event.preventDefault();
      event.key === 'Enter' ? first.click() : first.focus();
    }
  });
  results.addEventListener('keydown', event => {
    const links = [...results.querySelectorAll('a')];
    const position = links.indexOf(document.activeElement);
    if (position < 0) return;
    if (event.key === 'ArrowDown' && links[position + 1]) { event.preventDefault(); links[position + 1].focus(); }
    if (event.key === 'ArrowUp') { event.preventDefault(); (links[position - 1] || input).focus(); }
  });
  section.addEventListener('change', search);
  document.addEventListener('keydown', event => {
    const typing = event.target.closest('input, textarea, select, [contenteditable="true"]');
    if ((event.key === '/' && !typing) || ((event.ctrlKey || event.metaKey) && event.key === 'k')) { event.preventDefault(); openSearch(); }
  });

  /* ---- On-page contents ---- */
  const mobileToc = document.querySelector('.mobile-toc');
  const heading = document.querySelector('.prose h1');
  if (mobileToc && heading) {
    const lead = heading.nextElementSibling;
    (lead && lead.tagName === 'P' && !lead.querySelector('img') ? lead : heading).after(mobileToc);
    mobileToc.addEventListener('click', event => { if (event.target.closest('a')) mobileToc.open = false; });
  }
  const tocLinks = [...document.querySelectorAll('.page-toc a')];
  const sections = tocLinks.map(link => document.getElementById(decodeURIComponent(link.hash.slice(1)))).filter(Boolean);
  if (sections.length) {
    let frame;
    const header = document.querySelector('.site-header');
    const update = () => {
      frame = null;
      // The reading line sits a quarter of the way down the area below the
      // sticky header. The last heading above it is the one nearest the top
      // of the content, including a heading an anchor jump just scrolled to.
      const top = header ? header.getBoundingClientRect().bottom : 0;
      const line = top + Math.max(48, (innerHeight - top) * .25);
      let active = sections[0];
      for (const target of sections) { if (target.getBoundingClientRect().top <= line) active = target; else break; }
      // Sections near the end cannot scroll up to the line. At the bottom of
      // the page, prefer a linked section that is on screen, else the last one.
      if (innerHeight + scrollY >= document.documentElement.scrollHeight - 4) {
        const linked = document.getElementById(decodeURIComponent(location.hash.slice(1)));
        const box = linked && sections.includes(linked) && linked.getBoundingClientRect();
        active = box && box.top >= top && box.bottom <= innerHeight ? linked : sections[sections.length - 1];
      }
      tocLinks.forEach(link => link.classList.toggle('active', link.hash && decodeURIComponent(link.hash.slice(1)) === active.id));
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    addEventListener('scroll', schedule, {passive: true});
    addEventListener('resize', schedule);
    addEventListener('hashchange', schedule);
    update();
  }
})();
