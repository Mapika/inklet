"""Keep repository-relative Markdown useful in both GitHub and MkDocs.

Gallery images are included from their existing location. Links to source
outside docs/ point at the GitHub repository.
"""
from pathlib import Path
import ast
import hashlib
import json
import os
import posixpath
import re
import tomllib
from urllib.parse import quote, unquote, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
LINK = re.compile(r'(!?\[[^\]\n]*\])\(([^\s)]+)\)')
FENCE = re.compile(r'(^```[^\n]*\n.*?^```[^\n]*$)', re.MULTILINE | re.DOTALL)


def on_files(files, config):
    from mkdocs.structure.files import File
    for path in sorted((ROOT/'gallery').glob('*.png')):
        files.append(File(path.relative_to(ROOT).as_posix(),str(ROOT),
                          config['site_dir'],config['use_directory_urls']))
    return files


def repository_ref():
    """Link hosted examples to the revision used for this documentation build."""
    return (os.environ.get('READTHEDOCS_GIT_COMMIT_HASH')
            or os.environ.get('READTHEDOCS_GIT_IDENTIFIER') or 'master')


def on_config(config):
    # A deployed page must not reuse a previous theme's cached CSS or JS.
    assets = [*config['extra_css'], *config['extra_javascript']]
    digest = hashlib.sha256()
    for asset in assets:
        digest.update((DOCS/str(asset)).read_bytes())
    config['extra']['asset_version'] = (
        os.environ.get('READTHEDOCS_GIT_COMMIT_HASH') or digest.hexdigest()
    )[:12]
    # Navigation URLs bypass Markdown rewriting, but need the same revision.
    repo_url = config['repo_url'].rstrip('/')
    ref = quote(repository_ref(), safe='')

    def rewrite(value):
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, dict):
            return {key: rewrite(item) for key, item in value.items()}
        if isinstance(value, str):
            for kind in ('blob', 'tree'):
                prefix = f'{repo_url}/{kind}/master/'
                if value.startswith(prefix):
                    return f'{repo_url}/{kind}/{ref}/{value[len(prefix):]}'
        return value

    config['nav'] = rewrite(config['nav'])
    return config


def rewrite_links(markdown, source_path, repo_url, ref='master'):
    def replace(match):
        label, target = match.groups()
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group()
        path = (source_path.parent/unquote(parsed.path)).resolve()
        if path.is_relative_to(DOCS):
            return match.group()
        if not path.is_relative_to(ROOT) or not path.exists():
            raise ValueError(f'{source_path}: missing repository link {target}')
        relative = path.relative_to(ROOT).as_posix()
        if label.startswith('!') and path.parent == ROOT/'gallery' and path.suffix == '.png':
            parent = source_path.parent.relative_to(DOCS).as_posix()
            url = posixpath.relpath(relative,parent)
        else:
            kind = 'tree' if path.is_dir() else 'blob'
            url = f'{repo_url.rstrip("/")}/{kind}/{quote(ref, safe="")}/{quote(relative)}'
        parts = urlsplit(url)
        return f'{label}({urlunsplit((parts.scheme,parts.netloc,parts.path,parsed.query,parsed.fragment))})'
    # Examples may contain strings that resemble links; do not rewrite code.
    return ''.join(part if index%2 else LINK.sub(replace,part)
                   for index,part in enumerate(FENCE.split(markdown)))


def on_page_markdown(markdown, page, config, files):
    def recipe(match):
        source = (ROOT/'examples/showcase/figures.py').read_text()
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == match[1])
        return '```python\nimport math\nimport inklet as i\n\n\n' + ast.get_source_segment(source, function) + '\n```'
    markdown = re.sub(r'<!-- recipe:([a-z_]+) -->', recipe, markdown)
    return rewrite_links(markdown,Path(page.file.abs_src_path),config['repo_url'],repository_ref())


def on_page_context(context, page, config, nav):
    context['docs_gallery'] = json.loads((ROOT/'tools/docs_gallery.json').read_text())
    version = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
    context['docs_version'] = version.replace('.0.dev', ' dev ')
    return context
