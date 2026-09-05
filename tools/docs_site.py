"""Keep repository-relative Markdown useful in both GitHub and MkDocs.

Gallery images are included from their existing location. Links to source
outside docs/ point at the private repository and retain its access controls.
"""
from pathlib import Path
import posixpath
import re
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


def rewrite_links(markdown, source_path, repo_url):
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
            url = f'{repo_url.rstrip("/")}/{kind}/master/{quote(relative)}'
        parts = urlsplit(url)
        return f'{label}({urlunsplit((parts.scheme,parts.netloc,parts.path,parsed.query,parsed.fragment))})'
    # Examples may contain strings that resemble links; do not rewrite code.
    return ''.join(part if index%2 else LINK.sub(replace,part)
                   for index,part in enumerate(FENCE.split(markdown)))


def on_page_markdown(markdown, page, config, files):
    return rewrite_links(markdown,Path(page.file.abs_src_path),config['repo_url'])
