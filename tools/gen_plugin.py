"""Write the Claude Code plugin's generated files from the package.

    python tools/gen_plugin.py          # write
    python tools/gen_plugin.py --check  # exit 1 if a file is out of date

`plugins/inklet` is the plugin that `/plugin install inklet@inklet` installs.
Its skill body is what `inklet skill` installs, read back from `install_skill`
rather than copied, and its manifest carries the package version. Only the
front matter of the skill is the plugin's own, because the plugin's description
says when to load it. Run this after bumping the version.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import tomllib
from pathlib import Path

import inklet
import inklet.cli as cli
from inklet.agent import install_skill

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / 'plugins' / 'inklet'
MANIFEST = PLUGIN / '.claude-plugin' / 'plugin.json'
SKILL = PLUGIN / 'skills' / 'inklet' / 'SKILL.md'

PLUGIN_DESCRIPTION = ('Publication-quality figures from Python with inklet: one-call charts, '
                      'measured layout, and SVG/PDF/PNG export, with the agent guide as a skill.')
SKILL_DESCRIPTION = ('Use when the user wants a chart, plot, graph or publication figure made in Python, '
                     'especially for a journal paper, report or slide. Builds figures with the inklet '
                     'library: one-call charts, lettered multi-panel layouts, measured labels and '
                     'SVG/PDF/PNG export.')

_FRONT_MATTER = re.compile(r'---\n.*?\n---\n\n', re.DOTALL)


def _skill_body() -> str:
    """The text `inklet skill` writes after its front matter, for this source tree."""
    # install_skill stamps the version of the installed distribution, which can
    # be an older checkout's metadata; the plugin must describe this source tree.
    cli._version = lambda: inklet.__version__
    with tempfile.TemporaryDirectory() as scratch:
        installed = install_skill(scratch).read_text(encoding='utf-8')
    match = _FRONT_MATTER.match(installed)
    if match is None:
        raise RuntimeError('install_skill did not write front matter')
    return installed[match.end():]


def skill_md() -> str:
    # json.dumps gives a double-quoted YAML scalar, which is safe for any text.
    return ('---\nname: inklet\n'
            f'description: {json.dumps(SKILL_DESCRIPTION)}\n'
            '---\n\n' + _skill_body())


def plugin_json() -> str:
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    manifest = {
        'name': 'inklet',
        'version': inklet.__version__,
        'description': PLUGIN_DESCRIPTION,
        'author': {'name': 'Mapika'},
        'homepage': 'https://inklet.readthedocs.io',
        'repository': project['urls']['Repository'],
        'license': project['license'],
    }
    return json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'


OUTPUTS = {MANIFEST: plugin_json, SKILL: skill_md}


def main(argv):
    rendered = {path: render() for path, render in OUTPUTS.items()}
    if '--check' in argv:
        stale = [path for path, text in rendered.items()
                 if not path.exists() or path.read_text(encoding='utf-8') != text]
        for path in stale:
            print(f'{path} is out of date; run python tools/gen_plugin.py')
        return 1 if stale else 0
    for path, text in rendered.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        print(f'wrote {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
