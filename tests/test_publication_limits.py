"""Publication limits are checked against final transformed artwork."""
import pytest
import inklet as i


def codes(compiled):
    return {d.code for d in compiled.diagnostics}


@pytest.mark.parametrize('font,scale,too_large', [(7, 1, False), (8, 1, True),
                                                (14, .5, False), (4, 2, True)])
def test_nature_checks_effective_font_size(font, scale, too_large):
    doc = i.preset('scientific.nature').document()
    doc.add('label', i.text('Measured label', size=i.pt(font)).scaled(scale))
    compiled = doc.compile()
    assert ('LARGE_TEXT' in codes(compiled)) == too_large
    assert not any(d.code == 'LINT_RULE_FAILED' for d in compiled.diagnostics)
    assert ('LARGE_TEXT' in {d.code for d in compiled.lint()}) == too_large
    assert not any(d.code == 'LARGE_TEXT' for d in compiled.lint(max_font_pt=None))


@pytest.mark.parametrize('height,too_tall', [(170, False), (171, True)])
def test_nature_checks_page_height(height, too_tall):
    doc = i.preset('scientific.nature').document(height=height)
    doc.add('label', i.component(i.text, 'Figure'))
    compiled = doc.compile()
    assert ('PAGE_TOO_TALL' in codes(compiled)) == too_tall
    assert ('PAGE_TOO_TALL' in {d.code for d in compiled.lint()}) == too_tall


def test_auto_height_is_checked_and_other_destinations_are_unrestricted():
    doc = i.preset('scientific.nature').document()
    doc.add('plot', i.plot_spec(height=180).axes())
    assert 'PAGE_TOO_TALL' in codes(doc.compile())
    doc = i.preset('scientific.nature', format='slide').document()
    doc.add('title', i.component(i.title, 'Presentation'))
    assert not codes(doc.compile()) & {'LARGE_TEXT', 'PAGE_TOO_TALL'}
    assert i.publication().max_font_pt is None
    assert i.preset('scientific.nature').customize(max_height_mm=None).publication.max_height_mm is None


def test_nonuniform_scaling_cannot_hide_oversized_type():
    doc = i.preset('scientific.nature').document()
    doc.add('stretched', i.text('Stretched label', size=i.pt(7)).scaled(.5, 2))
    assert 'LARGE_TEXT' in codes(doc.compile())


@pytest.mark.parametrize('options', [dict(max_font_pt=0), dict(max_font_pt=4),
    dict(max_font_pt=float('nan')), dict(max_height_mm=-1), dict(max_height_mm=float('inf'))])
def test_invalid_publication_limits_fail_early(options):
    with pytest.raises(ValueError):
        i.preset('scientific.nature', **options)
