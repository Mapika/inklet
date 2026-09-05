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

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('a','link') and attrs.get('href'):
            self.references.append((tag,attrs['href']))
        if tag in ('img','script') and attrs.get('src'):
            self.references.append((tag,attrs['src']))


def test_strict_site_has_working_assets_search_and_rendered_examples(tmp_path):
    site = tmp_path/'site'
    build = subprocess.run([sys.executable,'-m','mkdocs','build','--strict',
                            '--site-dir',str(site)],cwd=ROOT,capture_output=True,text=True)
    assert build.returncode == 0, build.stdout+build.stderr
    pages = list(site.rglob('*.html'))
    assert len(pages) >= 25
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
            path = ((site/url.path.lstrip('/')) if url.path.startswith('/')
                    else (page.parent/unquote(url.path))).resolve()
            assert path.is_relative_to(site) and path.exists(), f'{page}: missing {target}'
    quickstart = (site/'quickstart/index.html').read_text()
    assert 'README example</a>' in quickstart
    assert 'class="codehilite"' in quickstart
    assert (site/'gallery/stress20.png').read_bytes() == (ROOT/'gallery/stress20.png').read_bytes()
    search = json.loads((site/'search/search_index.json').read_text())
    locations = {item['location'].split('#')[0] for item in search['docs']}
    assert {'data/','plotting/','api/','cli/','quickstart/'}.issubset(locations)
