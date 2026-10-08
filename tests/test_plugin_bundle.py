"""The Claude Code plugin must describe the package it ships with."""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import inklet

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / 'plugins' / 'inklet'


def test_generated_plugin_files_are_current():
    """`plugin.json` and `SKILL.md` are `tools/gen_plugin.py` output; rerun it after a version bump."""
    done = subprocess.run(
        [sys.executable, str(ROOT / 'tools' / 'gen_plugin.py'), '--check'],
        capture_output=True, text=True, cwd=ROOT)

    assert done.returncode == 0, done.stdout + done.stderr


def test_marketplace_lists_the_plugin_and_its_version_matches_the_package():
    market = json.loads((ROOT / '.claude-plugin' / 'marketplace.json').read_text(encoding='utf-8'))
    assert market['name'] == 'inklet'
    [entry] = [plugin for plugin in market['plugins'] if plugin['name'] == 'inklet']
    assert (ROOT / entry['source']).resolve() == PLUGIN.resolve()

    manifest = json.loads((PLUGIN / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))
    declared = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    assert manifest['name'] == 'inklet'
    assert manifest['version'] == declared == inklet.__version__


def test_skill_has_front_matter_the_harness_reads():
    text = (PLUGIN / 'skills' / 'inklet' / 'SKILL.md').read_text(encoding='utf-8')
    front, _, body = text[len('---\n'):].partition('\n---\n')
    assert front.startswith('name: inklet\ndescription: "Use when ')
    assert 'inklet check' in body and 'i.line(df' in body
