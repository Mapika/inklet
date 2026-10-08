"""`inklet check` takes the figure an author script saves, as well as a `make_*`
factory or a module-level inklet object.

A script that only calls `.save()` is the natural one for a coding agent. The
script's own saves still write their files: the loader only notes them.
"""
import json
import textwrap

import pytest

from inklet.cli import load_figure, main
from inklet.quick import _Renderable


def _script(tmp_path, text, name='author.py'):
    path = tmp_path / name
    path.write_text(textwrap.dedent(text))
    return path


SAVE_ONLY = '''
    import inklet as i
    i.line({'x': [1, 2, 3], 'y': [1, 4, 9]}, x='x', y='y').save('fig.pdf')
'''


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_check_accepts_a_script_that_only_saves_its_figure(workdir, capsys):
    script = _script(workdir, SAVE_ONLY)
    assert main(['check', str(script)]) == 0
    assert 'lint: clean' in capsys.readouterr().out


def test_check_json_reports_the_saved_figure(workdir, capsys):
    script = _script(workdir, SAVE_ONLY)
    assert main(['check', str(script), '--json']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['ok'] is True
    assert report['size_mm'][0] > 0 and report['diagnostics'] == []


def test_the_script_still_writes_the_file_it_saves(workdir):
    script = _script(workdir, SAVE_ONLY)
    main(['check', str(script)])
    assert (workdir / 'fig.pdf').read_bytes().startswith(b'%PDF')


def test_the_saved_figure_is_preferred_to_unnamed_module_level_charts(workdir):
    script = _script(workdir, '''
        import inklet as i
        i.line({'x': [1, 2], 'y': [1, 2]}, x='x', y='y', title='Saved one').save('a.svg')
        i.line({'x': [1, 2], 'y': [2, 1]}, x='x', y='y', title='Unsaved two')
        i.line({'x': [1, 2], 'y': [3, 1]}, x='x', y='y', title='Unsaved three')
    ''')
    assert 'Saved one' in load_figure(script).to_svg()


def test_the_last_saved_figure_is_the_one_checked(workdir):
    script = _script(workdir, '''
        import inklet as i
        first = i.line({'x': [1, 2], 'y': [1, 2]}, x='x', y='y', title='First saved')
        second = i.line({'x': [1, 2], 'y': [2, 1]}, x='x', y='y', title='Second saved')
        first.save('a.svg')
        second.save('b.svg')
    ''')
    assert 'Second saved' in load_figure(script).to_svg()


def test_a_make_factory_still_wins_over_a_saved_figure(workdir):
    script = _script(workdir, '''
        import inklet as i
        i.line({'x': [1, 2], 'y': [1, 2]}, x='x', y='y', title='Saved').save('a.svg')

        def make_chart():
            return i.line({'x': [1, 2], 'y': [2, 1]}, x='x', y='y', title='Factory')
    ''')
    assert 'Factory' in load_figure(script).to_svg()


def test_the_save_methods_are_restored_after_the_script_runs(workdir):
    original = _Renderable.__dict__['save']
    load_figure(_script(workdir, SAVE_ONLY))
    assert _Renderable.__dict__['save'] is original


def test_a_script_with_nothing_to_check_says_it_can_save_a_chart(workdir, capsys):
    script = _script(workdir, 'x = 1\n')
    with pytest.raises(ValueError, match='or save a chart in the script'):
        load_figure(script)
    assert main(['check', str(script)]) == 1
    assert 'or save a chart in the script' in capsys.readouterr().err
