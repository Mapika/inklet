"""Why no shipped role sets `font_style`, stated as a measurement.

Round 3 declined an italic caption/axis-label role on editorial grounds: a
journal caption is roman, an axis label is roman, and italic in a figure means
something specific -- a variable, a species name, an emphasis the author chose
-- so a role that italicised a whole class of text would leave `//x//` inside
it with nothing to say. `test_no_shipped_role_is_italic` records that.

This file is the second look, and it found a mechanical reason underneath the
editorial one. A role's `font_style` is applied where every other role field is
applied: as an attribute on the group, at render. The shaper never sees it, so
the line is *measured* in the roman face and *painted* slanted -- the advances
are the roman ones and the glyphs are not. The real italic face of the default
family is 5.4% narrower, so a 62mm caption is set 3.3mm too wide and the words
either side of a space run together. A role-level italic is not the same object
as `inklet.text(font_style="italic")`, which is measured in the italic face and is
correct; the role table is the wrong place to reach for one until the shaper
reads it.

Crop: `tmp/agents/r6-annot/font_style/font_style-declined.png`.
"""

from __future__ import annotations

import dataclasses
import re

import inklet
from inklet.themes.theme import Theme

CAPTION = "Growth of //E. coli// K-12 at 37 C, mean of three replicates."


def rendered(*, italic_role: bool) -> str:
    """`CAPTION` in the `emphasis` role, with that role optionally italic."""
    real = Theme.style_for
    if italic_role:
        Theme.style_for = lambda self, role: (        # noqa: E731
            dataclasses.replace(real(self, role), font_style="italic")
            if role == "emphasis" else real(self, role))
    try:
        fig = inklet.figure(width="96mm", theme="nature")
        fig.add(inklet.Diagram(prim=inklet.shape(CAPTION, size=2.4, width=88.0),
                            kind="emphasis"))
        return fig.to_svg()
    finally:
        Theme.style_for = real


def advances(svg: str) -> list[str]:
    """Every `x` a tspan was placed at: the shaper's answer, in the output."""
    line = [l for l in svg.splitlines() if "Growth of" in l][0]
    return re.findall(r'x="(-?[\d.]+)"', line)


def test_a_role_level_italic_is_painted_but_not_measured():
    """The mechanical half of the decline. Identical advances under a
    different face is a line set to the wrong width -- and if this ever stops
    being true, the editorial argument is the only one left and the item can
    be reopened on it."""
    assert advances(rendered(italic_role=False)) == advances(
        rendered(italic_role=True))


def test_the_two_faces_are_not_the_same_width():
    """Which is what makes the paragraph above a defect rather than a
    technicality: it is 3.3mm on a 62mm caption, one whole word."""
    plain = "Growth of E. coli K-12 at 37 C, mean of three replicates."
    roman = inklet.text(plain, size=2.4).bbox.width
    italic = inklet.text(plain, size=2.4, font_style="italic").bbox.width

    assert italic < roman - 1.0


def test_the_markup_the_author_wrote_survives_the_roman_role():
    """The editorial half, from the other side: `//E. coli//` is a slanted run
    inside an upright line, and that is the only reading of italic the figure
    has. Under an italic role the same run is slanted inside a slanted line
    and says nothing."""
    marked = rendered(italic_role=False)

    assert marked.count('font-style="italic"') == 1
