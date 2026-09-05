"""Shaped text as individual glyph placements, for backends that reuse them.

`inklet.typeset.outline.text_to_paths` hands back a text block as merged geometry
-- one `PathPrim` per colour in it, holding every contour of every occurrence
of every letter, already in the block's frame. That is the right shape for a
tree transform and for PDF, which has no way to say "this letter again", and
the wrong one for SVG, which does: `<defs>` holds one `<path>` per distinct
glyph and each occurrence after that is a thirty-byte `<use>`.

So the walk is done once here, at a lower level: the same shaping, the same
cached contours, the same arithmetic, but stopping at *(face, glyph, size, pen
position)* instead of collecting geometry. `to_path` merges it back and
returns contour for contour what `text_to_paths` builds for the same block,
which is how the two spellings of an outlined figure stay the same figure.

Per-glyph colour rides along, because merging is where it is lost: a
`TextRun.fill` paints those glyphs and no others, and a backend holding one
path per colour can no longer put a halo behind all of them at once or write
the block as a single run of live text.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.geom import Vec2
from ..core.prims import PathPrim, Subpath, TextLine, TextPrim
from ..typeset.fonts import FontFace, load_face
from ..typeset.outline import placed_contours
from ..typeset.shaping import feature_key, shape_buffer

__all__ = ["PlacedGlyph", "placed_glyphs", "glyph_outline", "to_path"]


@dataclass(frozen=True, slots=True)
class PlacedGlyph:
    """One glyph of a shaped block, where the shaper put it.

    `origin` is the pen point in the text block's own frame (y down, the block
    centred on it, exactly as `TextPrim` is), and `size` is the em size *this*
    glyph is drawn at -- a subscript run sets its own. Together with the face
    and the glyph id that is everything needed either to draw the outline or to
    look up one already drawn.
    """

    font_path: str
    font_index: int
    gid: int
    size: float
    origin: Vec2
    #: The run's own colour, or None to take the text node's. See `TextRun.fill`.
    fill: str | None = None
    #: The characters this glyph came from, on the first glyph of a shaping
    #: cluster and empty on the rest of it -- so a `fi` ligature carries "fi"
    #: and an accent carries nothing, its base having carried both. Only a
    #: backend writing live text reads it (PDF's `/ToUnicode`); it is not part
    #: of `key`, because two occurrences of a letter are the same drawing
    #: whatever text they were spelled from.
    chars: str = ""

    @property
    def key(self) -> tuple[str, int, int, float]:
        """What two occurrences of the same letter share: face, glyph, size."""
        return (self.font_path, self.font_index, self.gid, self.size)


def placed_glyphs(prim: TextPrim) -> list[PlacedGlyph]:
    """Every glyph of a shaped text block, in drawing order.

    The block is reshaped under the features it was *measured* with, which it
    carries itself: `TextPrim.features`, which `inklet.typeset.shape` has recorded
    since the 2026-08-23 amendment. There is deliberately no way to pass a
    different set -- shaping under rules the advances never saw places glyphs
    by one metric inside a layout built on another, and ten tabular digits
    drift 2.8mm over ten characters. That was a parameter here until the field
    existed to make it unnecessary.

    Raises ValueError if the prim has no `font_path` -- it did not come from
    `inklet.typeset.shape` and there is no face to reopen.
    """
    if not prim.lines:
        return []
    if prim.font_path is None:
        raise ValueError(
            "cannot outline a TextPrim with no font_path; build it with inklet.typeset.shape()"
        )
    face = load_face(prim.font_path)
    otf = feature_key(dict(getattr(prim, "features", ())))

    out: list[PlacedGlyph] = []
    for line in prim.lines:
        if not line.text:
            continue
        pen_x = -prim.width / 2 + prim.line_offset(line)
        pen_y = prim.first_baseline + line.baseline
        for text, run_face, size, shift, fill in _spans(line, face, prim.font_size):
            if not text:
                continue
            scale = run_face.scale(size)
            buffer = shape_buffer(text, run_face, otf)
            spelling = _cluster_text(buffer, text)
            for index, (info, position) in enumerate(
                    zip(buffer.glyph_infos, buffer.glyph_positions)):
                out.append(PlacedGlyph(
                    font_path=run_face.path,
                    font_index=run_face.index,
                    gid=info.codepoint,
                    size=size,
                    origin=Vec2(pen_x + position.x_offset * scale,
                                pen_y + shift - position.y_offset * scale),
                    fill=fill,
                    chars=spelling[index],
                ))
                pen_x += position.x_advance * scale
                pen_y -= position.y_advance * scale
                # Justification slack is paid at each space, not banked to the
                # end of the run: a run now ends mid-line wherever markup
                # changes, and banking it would open one five-space hole in
                # front of every bold word. `info.cluster` indexes the run's
                # own string, so this asks the character rather than the glyph.
                if line.word_spacing and text[info.cluster] == " ":
                    pen_x += line.word_spacing
    return out


def _cluster_text(buffer, text: str) -> list[str]:
    """What each glyph of a shaped buffer spells, one entry per glyph.

    A shaping cluster is the smallest run of characters and glyphs that
    correspond to each other, and inside it the correspondence is unknowable
    -- one glyph may be three characters (a ligature) or three glyphs one
    character (a decomposed accent). So the whole cluster's text goes on its
    first glyph and the rest of the cluster gets nothing, which is what a PDF
    `/ToUnicode` map wants: copying the word out gives the characters back,
    once each, in order.

    Cluster values index `text` and are monotonic in either direction, so the
    span a value covers ends at the next larger value -- which is true for a
    right-to-left run without this having to know which way it ran.
    """
    clusters = [info.cluster for info in buffer.glyph_infos]
    if not clusters:
        return []
    bounds = sorted(set(clusters))
    ends = {start: (bounds[i + 1] if i + 1 < len(bounds) else len(text))
            for i, start in enumerate(bounds)}
    seen: set[int] = set()
    out = []
    for cluster in clusters:
        if cluster in seen:
            out.append("")
        else:
            seen.add(cluster)
            out.append(text[cluster:ends[cluster]])
    return out


def _spans(line: TextLine, face: FontFace,
           size: float) -> list[tuple[str, FontFace, float, float, str | None]]:
    """The line as (text, face, size, baseline shift, fill) -- one span unless a
    font was borrowed, a sub/superscript was set or a run was recoloured."""
    if not line.runs:
        return [(line.text, face, size, 0.0, None)]
    return [(run.text,
             load_face(run.font_path, run.font_index) if run.font_path else face,
             size if run.size is None else run.size,
             run.shift,
             getattr(run, "fill", None))
            for run in line.runs]


def glyph_outline(glyph: PlacedGlyph, origin: Vec2 = Vec2(0.0, 0.0)) -> list[Subpath]:
    """One glyph's outline in millimetres at its own size, around `origin`.

    The default origin gives the glyph in its own frame, which is the shape a
    `<defs>` entry holds; passing `glyph.origin` gives it where it belongs on
    the page. `inklet.typeset.placed_contours` does the work -- and the y flip,
    font space having y up -- off the same contour cache `text_to_paths` uses,
    so a letter this module draws is a letter that module has not had to walk.
    """
    face = load_face(glyph.font_path, glyph.font_index)
    return placed_contours(glyph.font_path, glyph.font_index, glyph.gid,
                           origin, face.scale(glyph.size))


def to_path(glyphs: list[PlacedGlyph]) -> PathPrim | None:
    """The glyphs merged into one filled path, or None when none of them inks.

    Contour for contour and in the same order, this is what
    `inklet.typeset.outline.text_to_paths` builds for the same block -- with the
    difference that it splits at each `{fill|text}` colour and this does not,
    so the two agree exactly on a block with no recoloured run in it and this
    one is the union of the other's paths otherwise. Callers that need the
    colours (both backends) read `PlacedGlyph.fill` and group for themselves;
    callers that need one shape (the halo pass) want the union.
    """
    subpaths: list[Subpath] = []
    for glyph in glyphs:
        subpaths += glyph_outline(glyph, glyph.origin)
    return PathPrim(tuple(subpaths), filled=True) if subpaths else None
