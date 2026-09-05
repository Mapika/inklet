"""Run user-facing guide examples and validate their repository links."""
from pathlib import Path
import importlib.util
import re
import shutil
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('README.md', 'docs/quickstart.md', 'docs/concepts.md', 'docs/layout.md',
         'docs/plotting.md', 'docs/data.md', 'docs/diagrams.md',
         'docs/three-images.md', 'docs/export-review.md', 'docs/cli.md', 'docs/presets.md')
BLOCK = re.compile(r'(?:(<!-- Requires preview renderers\. -->)\n\n)?^```python\n(.*?)^```',re.MULTILINE | re.DOTALL)


@pytest.mark.parametrize('relative', PAGES)
def test_guide_python_examples(relative, tmp_path, monkeypatch):
    import inklet as i
    original_theme = i.current_theme()
    monkeypatch.chdir(tmp_path)
    blocks = BLOCK.findall((ROOT/relative).read_text())
    assert blocks, f'{relative} has no Python examples'
    namespace = {'__name__': '__main__'}
    try:
        for index,(optional,code) in enumerate(blocks):
            if optional:
                continue
            exec(compile(code,f'{relative}:block-{index+1}','exec'),namespace)
    finally:
        i.use_theme(original_theme)


@pytest.mark.parametrize('relative', ('docs/quickstart.md','docs/export-review.md'))
def test_optional_review_examples(relative, tmp_path, monkeypatch):
    if (not importlib.util.find_spec('PIL') or not shutil.which('pdftoppm')
            or not any(shutil.which(n) for n in ('google-chrome','chromium','chromium-browser'))):
        pytest.skip('review examples need Pillow, Chrome/Chromium and Poppler')
    monkeypatch.chdir(tmp_path)
    namespace = {'__name__': '__main__'}
    for index,(_,code) in enumerate(BLOCK.findall((ROOT/relative).read_text())):
        exec(compile(code,f'{relative}:block-{index+1}','exec'),namespace)
    assert list(tmp_path.rglob('*-manifest.json'))


def test_documentation_links_resolve_inside_repository():
    pages = [ROOT/'README.md',ROOT/'CONTRIBUTING.md',*(ROOT/'docs').rglob('*.md')]
    missing = []
    for page in pages:
        prose = re.sub(r'^```[^\n]*\n.*?^```','',page.read_text(),flags=re.MULTILINE | re.DOTALL)
        for target in re.findall(r'!?\[[^\]\n]*\]\(([^\s)]+)\)',prose):
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            path = (page.parent/unquote(url.path)).resolve()
            if not path.is_relative_to(ROOT) or not path.exists():
                missing.append(f'{page.relative_to(ROOT)}: {target}')
    assert not missing, '\n'.join(missing)


def test_site_links_keep_gallery_local_and_repository_access_controlled():
    spec = importlib.util.spec_from_file_location('docs_site',ROOT/'tools/docs_site.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source = ROOT/'docs/examples.md'
    text = ('![Plate](../gallery/stress20.png)\n[Source](../examples/stress20.py)\n'
            '[Guide](quickstart.md#place-and-export)\n'
            '```python\nx = "[Source](../examples/stress20.py)"\n```')
    result = module.rewrite_links(text,source,'https://github.com/Mapika/inklet')
    assert '![Plate](gallery/stress20.png)' in result
    assert '[Source](https://github.com/Mapika/inklet/blob/master/examples/stress20.py)' in result
    assert '[Guide](quickstart.md#place-and-export)' in result
    assert 'x = "[Source](../examples/stress20.py)"' in result
    with pytest.raises(ValueError,match='missing repository link'):
        module.rewrite_links('[missing](../no-such-file.py)',source,'https://github.com/Mapika/inklet')
