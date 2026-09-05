"""Preset inheritance, live edits, physical formats and export integration."""
from dataclasses import FrozenInstanceError
import importlib.util
import json
from pathlib import Path

import pytest
import inklet as i
from inklet.core.prims import TextPrim


def chart():
    return i.plot_spec(x=(0, 2), y=(0, 5)).line(
        [(0, 1), (1, 3), (2, 4)], name='Inherited').line(
        [(0, 2), (1, 2), (2, 3)], name='Explicit', stroke='#a12b35'
    ).axes(x='Time', y='Value').legend()


def texts(compiled):
    return [p.diagram.prim for p in compiled.build()[1].values()
            if isinstance(p.diagram.prim, TextPrim)]


@pytest.mark.parametrize('name,width,height', [('journal', 183, None),
    ('slide', 254, 142.875), ('worksheet', 210, 297)])
def test_complete_destination_examples_retain_physical_size(name, width, height):
    path = Path(__file__).resolve().parents[1]/'examples/preset_formats.py'
    spec = importlib.util.spec_from_file_location('preset_formats', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    compiled = getattr(module, f'make_{name}')().compile()
    assert compiled.root.width == width
    if height is not None:
        assert compiled.root.height == height
    else:
        assert compiled.root.height <= 170
    assert not compiled.diagnostics
    import re
    pdf = compiled.to_pdf()
    box = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]', pdf)
    assert box is not None
    assert float(box[1]) == pytest.approx(width*72/25.4, abs=.01)
    assert float(box[2]) == pytest.approx(compiled.root.height*72/25.4, abs=.01)
    assert f'width="{width}' in compiled.to_svg()


def kinds(compiled, kind):
    return [p for p in compiled.build()[1].values() if p.diagram.kind == kind]


@pytest.mark.parametrize('name', i.preset_names())
def test_every_preset_compiles_mixed_content_and_exports_vectors(name):
    path = Path(__file__).resolve().parents[1]/'examples/presets.py'
    spec = importlib.util.spec_from_file_location('preset_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    doc = module.make_document(name)
    compiled = doc.compile()
    assert compiled.root.width == i.preset(name).format.width
    assert compiled.to_pdf().startswith(b'%PDF')
    assert '<svg' in compiled.to_svg() and '<text' in compiled.to_svg()
    assert not {d.code for d in compiled.diagnostics} & {'LINT_RULE_FAILED', 'OFF_CANVAS', 'TINY_TEXT', 'KEY_MISMATCH', 'LARGE_TEXT', 'PAGE_TOO_TALL'}
    assert compiled.metadata['datasets'][0]['name'] == 'preset demonstration'
    assert compiled.metadata['preset']['name'] == name
    assert compiled.metadata['fonts']
    json.dumps(dict(compiled.metadata))
    assert doc.compile() is compiled


def test_switching_rebuilds_inherited_styles_and_preserves_explicit_choices():
    doc = i.preset('scientific.general').document(width=180, height=None, columns=2, gap=7)
    doc.add('chart', chart(), colspan=2)
    doc.add('explicit', i.component(i.text, 'Fixed label', size=i.pt(11), font='DejaVu Sans'))
    before = doc.compile()
    svg = before.to_svg()
    doc.use_preset(i.preset('marketing.report', accent='#635bff'))
    after = doc.compile()
    assert doc.width == 180 and doc.height is None and doc.gap == 7
    assert doc.columns == (1., 1.)
    assert after.to_svg() != svg and before.to_svg() == svg
    assert '#635bff' in after.to_svg() and '#a12b35' in after.to_svg()
    assert any(t.font_size == pytest.approx(i.pt(11)) for t in texts(after))
    assert kinds(after, 'gridline') and not kinds(before, 'gridline')
    assert doc['chart']._steps[0][3] == {'name': 'Inherited'}
    doc.configure(width=195, gap=9)
    doc.use_preset('educational.textbook')
    assert doc.width == 195 and doc.gap == 9
    doc.use_preset('scientific.general', keep_overrides=False)
    assert doc.width == 183 and doc.gap == 6 and doc.columns == (1., 1.)


def test_preset_change_invalidates_cache_even_when_only_plot_policy_changes():
    selected = i.preset()
    doc = selected.document()
    doc.add('chart', chart())
    first = doc.compile()
    doc.use_preset(selected.customize(grid='both'))
    second = doc.compile()
    assert kinds(second, 'gridline') and second is not first
    assert first.to_svg() != second.to_svg()
    assert doc.compile() is second


def test_explicit_grid_and_legend_options_override_preset_defaults():
    doc = i.preset('educational.textbook').document()
    plot = chart().grid(x=False, y=False)
    doc.add('chart', plot)
    compiled = doc.compile()
    assert not kinds(compiled, 'gridline')
    # A deliberately inside legend must not inherit the outside preset default.
    plot._steps[-2] = (None, 'legend', (), {'corner': 'ne'})
    inside = doc.compile()
    assert inside.to_svg() != compiled.to_svg()


def test_panel_letters_inherit_style_inside_nested_subfigures():
    child = i.subfigure().letters()
    child.add('module', i.module('Module'))
    doc = i.preset('scientific.general').document()
    doc.add('child', child)
    first = doc.compile()
    doc.use_preset('marketing.report')
    assert '>a<' in first.to_svg() and '>A<' in doc.compile().to_svg()
    child.letters(style='lower', size=i.pt(12))
    final = doc.compile()
    assert '>a<' in final.to_svg() and any(t.font_size == pytest.approx(i.pt(12)) for t in texts(final))


def test_custom_formats_branding_and_export_defaults(tmp_path, monkeypatch):
    selected = i.preset('marketing.report', format=i.FigureFormat('banner', 240, 80),
                        accent='#552299', font_family='DejaVu Sans', dpi=220, text='outline')
    assert selected.theme.accent == selected.theme.color(0) == '#552299'
    doc = selected.document()
    doc.add('module', i.module('Branded'))
    compiled = doc.compile()
    assert compiled.root.width == 240 and compiled.root.height == 80
    assert '<text' not in compiled.to_svg()
    import inklet.render.bundle as bundle
    monkeypatch.setattr(bundle, 'export_bundle', lambda figure, path, **kw: kw)
    assert compiled.export(tmp_path) == {'dpi': 220, 'text': 'outline'}
    assert compiled.metadata['preset']['format']['name'] == 'banner'
    assert i.preset('scientific.nature').theme.font_size == i.pt(7)
    assert i.preset('scientific.nature', format='slide').theme.font_size == i.pt(14)


def test_values_are_immutable_and_bad_changes_are_atomic():
    chosen = i.preset()
    with pytest.raises(FrozenInstanceError): chosen.gap = 20
    palette = ['#123456', '#abcdef']
    custom = chosen.customize(palette=palette)
    palette[0] = '#ffffff'
    assert custom.theme.palette[0] == '#123456'
    doc = chosen.document()
    with pytest.raises(ValueError): doc.use_preset('marketing.report', width=-1)
    assert doc.preset is chosen and doc.width == chosen.format.width
    with pytest.raises(TypeError): chosen.customize(unknown=3)
    with pytest.raises(ValueError): i.preset('missing')
    with pytest.raises(ValueError): i.preset(format='missing')
    with pytest.raises(ValueError): i.preset_names('missing')


@pytest.mark.parametrize('options', [dict(width=0), dict(height=float('nan')), dict(gap=-1),
    dict(margin=1000), dict(font_pt=0), dict(title_font_pt=-1), dict(dpi=float('inf')),
    dict(palette=[]), dict(accent='not a colour'), dict(grid='diagonal'),
    dict(tick_count=True), dict(legend_side='inside'), dict(font_family=''),
    dict(radius=-1), dict(line_height=0)])
def test_invalid_overrides_fail_at_selection(options):
    with pytest.raises((TypeError, ValueError)): i.preset(**options)


def test_legacy_publication_defaults_and_guideline_provenance():
    assert i.publication().theme == i.publication(base_theme='nature').theme
    assert i.publication(base_theme='slides').theme.palette == i.theme('slides').palette
    assert i.preset('scientific.nature').sources[0].reviewed_on == '2026-09-05'
    for name in ('scientific.science', 'scientific.cell'):
        assert i.preset(name).sources[0].status == 'unverified'
        assert i.preset(name).sources[0].reviewed_on is None


@pytest.mark.parametrize('format', i.format_names())
def test_physical_formats_compile_at_their_declared_dimensions(format):
    selected = i.preset(format=format)
    doc = selected.document()
    doc.add('plot', chart())
    compiled = doc.compile()
    assert compiled.root.width == selected.format.width
    if selected.format.height is not None:
        assert compiled.root.height == selected.format.height
    assert not {d.code for d in compiled.diagnostics} & {'LINT_RULE_FAILED', 'OFF_CANVAS', 'TINY_TEXT'}


def test_live_data_and_snapshots_survive_a_preset_change():
    data = i.dataset({'x': [0, 1], 'y': [1, 2]}, name='live')
    plot = i.plot_spec(x=(0, 1), y=(0, 5)).line(data.points('x', 'y')).axes()
    doc = i.preset().document()
    doc.add('plot', plot)
    original = doc.compile()
    svg = original.to_svg()
    doc.use_preset('marketing.report')
    styled = doc.compile()
    assert styled.metadata['datasets'] == original.metadata['datasets']
    data.update(y=[2, 4])
    updated = doc.compile()
    assert updated.metadata['datasets'][0]['revision'] == 1
    assert updated.metadata['datasets'][0]['data_sha256'] != original.metadata['datasets'][0]['data_sha256']
    assert updated.to_svg() != styled.to_svg() and original.to_svg() == svg


def test_bar_defaults_follow_brand_and_keep_explicit_colours_and_matching_keys():
    doc = i.preset('marketing.report', accent='#552299').document(columns=2)
    auto = i.plot_spec(x=i.band(['A', 'B']), y=(0, 5)).bars(['A', 'B'], [2, 3], names=['Values']).axes().legend()
    explicit = i.plot_spec(x=i.band(['A', 'B']), y=(0, 5)).bars(['A', 'B'], [2, 3], fill='#a12b35').axes()
    doc.add('auto', auto, row=0, column=0)
    doc.add('explicit', explicit, row=0, column=1)
    compiled = doc.compile()
    assert '#552299' in compiled.to_svg() and '#a12b35' in compiled.to_svg()
    assert not any(d.code == 'KEY_MISMATCH' for d in compiled.diagnostics)
    assert 'fill' not in auto._steps[0][3]
