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


def _letters(root):
    """Every panel letter in a compiled page, as (text, font size in pt, weight)."""
    found, stack = [], [root]
    while stack:
        node = stack.pop()
        if node.kind == 'letter' and node.prim is not None:
            found.append((node.prim.text, round(node.prim.font_size / i.pt(1), 3),
                          node.style.font_weight if node.style else None))
        stack.extend(node.children)
    return sorted(found)


def _two_panels(**options):
    rows = [dict(x=k, y=k * k) for k in range(5)]
    return i.Layout('row', [i.line(rows, x='x', y='y', style='scientific.nature'),
                            i.scatter(rows, x='x', y='y', style='scientific.nature')],
                    style='scientific.nature', **options)


def test_nature_panel_letters_are_8pt_bold_lowercase_and_pass_lint():
    # Nature: panel labels 8 pt bold upright lowercase; all other text 5-7 pt.
    profile = i.preset('scientific.nature').publication
    assert (profile.letter_font_pt, profile.max_letter_pt) == (8, 8)
    assert i.preset('scientific.nature', format='slide').publication.max_letter_pt is None
    compiled = _two_panels().compile()
    assert _letters(compiled.root) == [('a', 8.0, 'bold'), ('b', 8.0, 'bold')]
    assert not any(d.code == 'LARGE_TEXT' for d in compiled.lint())
    assert not any(d.code == 'LARGE_TEXT' for d in compiled.lint(min_font_pt=5))


def test_nature_lint_accepts_explicit_8pt_letters_but_not_larger():
    doc = _two_panels().document()
    doc.letters(size=i.pt(8))
    assert not any(d.code == 'LARGE_TEXT' for d in doc.compile().lint())
    doc.letters(size=i.pt(9))
    large = [d for d in doc.compile().lint() if d.code == 'LARGE_TEXT']
    assert len(large) == 2
    assert 'panel-letter maximum' in large[0].message and '8.0pt' in large[0].message


def test_letter_exemption_does_not_cover_other_8pt_text():
    doc = i.preset('scientific.nature').document()
    doc.add('label', i.text('Measured label', size=i.pt(8)))
    assert 'LARGE_TEXT' in codes(doc.compile())
    assert 'LARGE_TEXT' in {d.code for d in doc.compile().lint(max_letter_pt=8)}


def test_letter_size_follows_quick_font_pt_and_slide_scale():
    assert i.preset('scientific.nature', format='slide').publication.letter_font_pt == 16
    compiled = _two_panels(font_pt=6).compile()
    assert {size for _, size, _ in _letters(compiled.root)} == {round(8 * 6 / 7, 3)}


def test_profiles_without_a_letter_size_keep_title_sized_letters():
    assert i.preset('scientific.general').publication.letter_font_pt is None
    assert i.publication().letter_font_pt is None
