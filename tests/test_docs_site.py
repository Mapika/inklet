"""Build and inspect the actual documentation output when docs extras exist."""
from html.parser import HTMLParser
from pathlib import Path
import json
import subprocess
import sys
from urllib.parse import unquote, urlsplit

import pytest

pytest.importorskip('mkdocs')
pytest.importorskip('pygments')
ROOT = Path(__file__).resolve().parents[1]


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        # Canonical URLs identify the hosted page; they are not fetched assets.
        if tag == 'link' and 'canonical' in attrs.get('rel', '').split():
            return
        if tag in ('a','link') and attrs.get('href'):
            self.references.append((tag,attrs['href']))
        if tag in ('img','script') and attrs.get('src'):
            self.references.append((tag,attrs['src']))


def test_strict_site_has_working_assets_search_and_rendered_examples(tmp_path, monkeypatch):
    from mkdocs.config import load_config

    # Stable/tagged docs must link to their own source, including navigation.
    commit = '44df92a56a7f83ad9f4667901bf877582a817b63'
    monkeypatch.setenv('READTHEDOCS_GIT_COMMIT_HASH', commit)
    monkeypatch.setenv('READTHEDOCS_GIT_IDENTIFIER', 'v2.6.0')
    config = load_config(str(ROOT / 'mkdocs.yml'))
    site_prefix = urlsplit(config['site_url']).path
    site = tmp_path/'site'
    build = subprocess.run([sys.executable,'-m','mkdocs','build','--strict',
                            '--site-dir',str(site)],cwd=ROOT,capture_output=True,text=True)
    assert build.returncode == 0, build.stdout+build.stderr
    pages = list(site.rglob('*.html'))
    assert len(pages) >= 25
    parsed_pages = {}
    for page in pages:
        parser = References();parser.feed(page.read_text())
        parsed_pages[page.resolve()] = parser
    for page in pages:
        html = page.read_text()
        assert '<p>```' not in html, f'malformed code fence in {page}'
        parser = References();parser.feed(html)
        for tag,target in parser.references:
            url = urlsplit(target)
            if url.scheme or url.netloc:
                assert tag == 'a', f'external page asset: {target}'
                continue
            if not url.path:
                continue
            if url.path.startswith('/'):
                # MkDocs' 404 page uses absolute paths under the hosting prefix.
                assert url.path.startswith(site_prefix), f'outside site prefix: {target}'
                path = (site/unquote(url.path.removeprefix(site_prefix))).resolve()
            else:
                path = (page.parent/unquote(url.path)).resolve()
            assert path.is_relative_to(site) and path.exists(), f'{page}: missing {target}'
            destination = path/'index.html' if path.is_dir() else path
            if url.fragment and destination in parsed_pages:
                assert unquote(url.fragment) in parsed_pages[destination].ids, f'{page}: missing anchor {target}'
    quickstart = (site/'quickstart/index.html').read_text()
    assert 'README example</a>' in quickstart
    assert 'class="codehilite"' in quickstart
    assert f'inklet.css?v={commit[:12]}' in quickstart
    assert f'inklet.js?v={commit[:12]}' in quickstart
    assert 'search/main.js' not in quickstart
    assert f'https://github.com/Mapika/inklet/blob/{commit}/README.md' in quickstart
    assert f'https://github.com/Mapika/inklet/blob/{commit}/CONTRIBUTING.md' in quickstart
    assert 'https://github.com/Mapika/inklet/blob/master/' not in quickstart
    assert (site/'gallery/stress20.png').read_bytes() == (ROOT/'gallery/stress20.png').read_bytes()
    search = json.loads((site/'search/search_index.json').read_text())
    locations = {item['location'].split('#')[0] for item in search['docs']}
    assert {'data/','plotting/','api/','cli/','quickstart/'}.issubset(locations)
    assert {'recipes/interference/', 'recipes/architecture/', 'brand/'}.issubset(locations)
    recipe = (site/'recipes/interference/index.html').read_text()
    assert 'recipe:interference' not in recipe
    assert 'interference' in recipe and 'math' in recipe
    assert f'https://github.com/Mapika/inklet/blob/{commit}/examples/showcase/figures.py' in recipe
    gallery = json.loads((ROOT/'tools/docs_gallery.json').read_text())
    for entry in gallery:
        assert (site/entry['image']).is_file()
        location = urlsplit(entry['page'])
        destination = (site/location.path/'index.html').resolve()
        assert destination in parsed_pages
        if location.fragment:
            assert location.fragment in parsed_pages[destination].ids
