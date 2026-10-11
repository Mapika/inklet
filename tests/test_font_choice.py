"""Choosing a font by file, checking the families a destination expects, and
how PDF embeds text (TrueType CID fonts, the equivalent of Type 42)."""
from __future__ import annotations

import warnings
from pathlib import Path

import pytest

import inklet as i
from inklet.typeset import shape
from inklet.typeset.fonts import FontNotFoundError, find_font, load_face


def _regular():
    face = find_font('sans')
    if not face.path.lower().endswith('.ttf'):
        pytest.skip('the default sans face is not a TrueType file')
    return face


def _bold_sibling(face):
    for path in sorted(Path(face.path).parent.iterdir()):
        if path.suffix.lower() != '.ttf':
            continue
        other = load_face(str(path))
        if other.family == face.family and other.weight == 700 and not other.italic:
            return other
    pytest.skip(f'{face.family} has no bold file beside {face.path}')


def _arial_missing():
    if find_font('Arial').family.casefold() in ('arial', 'helvetica'):
        pytest.skip('Arial is installed here')


def test_a_font_file_in_a_family_chain_is_used_and_missing_files_are_skipped():
    face = _regular()
    chain = f'/no/such/dir/Arial.ttf, {face.path}, sans-serif'
    assert find_font(chain).path == face.path
    prim = shape('Encoder', font=chain)
    assert prim.font_path == face.path
    # The file is what was asked for, so it is not a substitution.
    assert prim.requested_family is None
    assert shape('Encoder', font=face.path).requested_family is None


def test_a_chain_whose_files_are_all_missing_falls_back_to_its_names():
    assert find_font('/no/such/Arial.ttf, sans-serif').path == find_font('sans-serif').path
    with pytest.raises(FontNotFoundError):
        find_font('/no/such/Arial.ttf')


def test_bold_and_italic_of_a_font_file_come_from_its_directory():
    face = _regular()
    bold = _bold_sibling(face)
    assert find_font(face.path, 'bold').path == bold.path
    assert find_font(f'{face.path}, sans-serif', 'bold').path == bold.path
    assert find_font(face.path).path == face.path


def test_a_preset_can_name_its_font_file_and_letters_use_its_bold():
    face = _regular()
    bold = _bold_sibling(face)
    style = i.preset('scientific.nature', font_family=f'{face.path}, sans-serif',
                     expected_fonts=(face.family,))
    d = {'x': [1, 2, 3], 'y': [2, 1, 3]}
    layout = i.Layout('row', [i.scatter(d, x='x', y='y', style=style),
                              i.scatter(d, x='x', y='y', style=style)], style=style)
    figure = layout.compile()
    paths, stack = set(), [figure.root]
    while stack:
        node = stack.pop()
        if getattr(node.prim, 'font_path', None):
            paths.add(node.prim.font_path)
        stack.extend(node.children)
    assert paths == {face.path, bold.path}
    assert not [d for d in figure.lint() if d.code == 'FONT_SUBSTITUTED']


def test_nature_warns_when_text_is_not_in_arial_or_helvetica():
    _arial_missing()
    assert i.preset('scientific.nature').publication.expected_fonts == ('Arial', 'Helvetica')
    doc = i.preset('scientific.nature').document()
    doc.add('label', i.text('Measured label'))
    found = [d for d in doc.compile().lint() if d.code == 'FONT_SUBSTITUTED']
    assert len(found) == 1 and found[0].severity == 'warning'
    assert "not in 'Arial' or 'Helvetica'" in found[0].message
    assert 'font_family=' in found[0].hint and '.ttf' in found[0].hint
    assert found == [d for d in doc.compile().diagnostics if d.code == 'FONT_SUBSTITUTED']
    quiet = i.preset('scientific.nature', expected_fonts=None).document()
    quiet.add('label', i.text('Measured label'))
    assert not [d for d in quiet.compile().lint() if d.code == 'FONT_SUBSTITUTED']


def test_monospaced_text_is_not_held_to_the_expected_fonts():
    _arial_missing()
    doc = i.preset('scientific.nature').document()
    doc.add('seq', i.text('MKTAYIAKQR', font='monospace'))
    found = [d for d in doc.compile().lint() if d.code == 'FONT_SUBSTITUTED']
    assert found == []
    doc.add('label', i.text('Measured label'))
    found = [d for d in doc.compile().lint() if d.code == 'FONT_SUBSTITUTED']
    assert len(found) == 1 and len(found[0].targets) == 1


def test_other_presets_expect_no_particular_font():
    assert i.preset('scientific.general').publication.expected_fonts is None
    assert i.publication().expected_fonts is None


def test_expected_fonts_must_be_family_names():
    with pytest.raises(ValueError):
        i.preset('scientific.nature', expected_fonts=('',))
    with pytest.raises(TypeError):
        i.preset('scientific.nature', expected_fonts='Arial')


def test_nature_pdf_embeds_text_as_truetype_cid_fonts():
    d = {'x': [1, 2, 3], 'y': [2, 1, 3]}
    pdf = i.scatter(d, x='x', y='y', style='scientific.nature').compile().to_pdf()
    assert b'/FontFile2' in pdf and b'/CIDFontType2' in pdf
    assert b'/Type3' not in pdf and b'/FontFile3' not in pdf


def test_a_cff_face_warns_when_pdf_must_outline_it():
    cff = next((p for p in sorted(Path('/usr/share/fonts').rglob('*.otf'))
                if 'Sans' in p.name and 'Regular' in p.name), None)
    if cff is None:
        pytest.skip('no CFF OpenType font installed')
    doc = i.document(width=60)
    doc.add('label', i.text('Measured label', font=str(cff)))
    figure = doc.compile()
    with pytest.warns(i.FontEmbeddingWarning, match='outlines its text'):
        figure.to_pdf(text='embed')
    with warnings.catch_warnings():
        warnings.simplefilter('error', i.FontEmbeddingWarning)
        figure.to_pdf(text='outline')
