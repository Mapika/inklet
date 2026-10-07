"""Which figure `inklet build` and `inklet check` take from an author script.

The choice is by type: a `make_*` factory if one is defined, else the module
level inklet object. A matplotlib `fig` next to an inklet `chart` must not
decide the build, and a script with no inklet object must say what it found.
"""
import importlib.metadata
import textwrap

import pytest

import inklet
from inklet.cli import load_figure, main


def _script(tmp_path, text, name='author.py'):
    path = tmp_path / name
    path.write_text(textwrap.dedent(text))
    return path


def test_an_inklet_chart_beside_a_matplotlib_figure_is_the_one_built(tmp_path):
    pytest.importorskip('matplotlib')
    script = _script(tmp_path, '''
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import inklet as i
        fig, ax = plt.subplots()
        ax.plot([1, 2], [3, 4])
        chart = i.line(x=[1, 2, 3], y=[2, 4, 3], title='Picked chart')
    ''')
    assert 'Picked chart' in load_figure(script).to_svg()


@pytest.mark.parametrize('names,chosen', [
    (('figure', 'doc'), 'doc'),
    (('fig', 'chart'), 'chart'),
    (('figure', 'fig'), 'fig'),
])
def test_a_preferred_name_wins_over_other_inklet_figures(tmp_path, names, chosen):
    lines = [f"{name} = i.line(x=[1, 2], y=[3, 4], title='{name} title')" for name in names]
    script = _script(tmp_path, 'import inklet as i\n' + '\n'.join(lines) + '\n')
    svg = load_figure(script).to_svg()
    assert f'{chosen} title' in svg
    assert all(f'{name} title' not in svg for name in names if name != chosen)


def test_a_single_unnamed_inklet_figure_is_used(tmp_path):
    script = _script(tmp_path, '''
        import inklet as i
        values = [1, 2, 3]
        plot = i.line(x=[1, 2], y=[3, 4], title='Lone plot')
    ''')
    assert 'Lone plot' in load_figure(script).to_svg()


def test_a_make_factory_wins_over_module_level_figures(tmp_path):
    script = _script(tmp_path, '''
        import inklet as i
        chart = i.line(x=[1, 2], y=[3, 4], title='Module chart')
        def make_chart():
            return i.bar(x=['a', 'b'], y=[1, 2], title='Factory chart')
    ''')
    svg = load_figure(script).to_svg()
    assert 'Factory chart' in svg and 'Module chart' not in svg


def test_a_factory_result_of_the_wrong_type_names_the_factory(tmp_path):
    script = _script(tmp_path, '''
        def make_document():
            return 'not a figure'
    ''')
    with pytest.raises(TypeError, match=r'make_document\(\) returned str'):
        load_figure(script)


def test_two_unnamed_inklet_figures_are_an_error_that_names_them(tmp_path):
    script = _script(tmp_path, '''
        import inklet as i
        left = i.line(x=[1, 2], y=[3, 4])
        right = i.bar(x=['a', 'b'], y=[1, 2])
    ''')
    with pytest.raises(ValueError, match='several unnamed inklet figures') as error:
        load_figure(script)
    assert 'left, right' in str(error.value)
    assert 'name the one to build `chart`' in str(error.value)


def test_a_lone_dataframe_gets_a_message_listing_what_was_found(tmp_path, capsys):
    pytest.importorskip('pandas')
    script = _script(tmp_path, '''
        import pandas as pd
        df = pd.DataFrame({'x': [1, 2]})
    ''')
    with pytest.raises(ValueError, match='defines no figure') as error:
        load_figure(script)
    message = str(error.value)
    assert 'df (' in message and 'DataFrame)' in message
    assert 'make_document()' in message and 'chart = i.line' in message

    assert main(['build', str(script)]) == 1
    assert 'Inklet: ValueError: author script defines no figure' in capsys.readouterr().err


def test_a_script_with_no_module_level_names_says_none(tmp_path):
    script = _script(tmp_path, 'x = 1\n')
    with pytest.raises(ValueError, match=r'Module-level names found: x \(int\)'):
        load_figure(script)
    empty = _script(tmp_path, 'def helper():\n    return 1\n', name='helpers.py')
    with pytest.raises(ValueError, match='Module-level names found: none'):
        load_figure(empty)


def test_the_guide_starts_with_the_installed_version(capsys):
    assert main(['guide']) == 0
    first = capsys.readouterr().out.splitlines()[0]
    assert first == f'inklet {importlib.metadata.version("inklet")}'


def test_the_guide_version_falls_back_to_the_package_attribute(monkeypatch):
    from inklet import cli

    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, 'version', missing)
    assert cli._version() == inklet.__version__
