"""Regression checks for the synthetic neural-activity example."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from figures import neural_activity as mouse
from figures import mouse_brain_data as data

def test_the_simulated_data_are_seeded_not_sampled():
    """The data module is asked twice and answers the same, which is the
    property the figure's determinism actually rests on."""
    assert data.learning("ChR2") == data.learning("ChR2")
    assert data.spike_trains() == data.spike_trains()
    assert data.permutation_p(data.endpoint("ChR2"), data.endpoint("eYFP")) \
        == data.permutation_p(data.endpoint("ChR2"), data.endpoint("eYFP"))


def test_panel_e_draws_every_animal_where_it_can_be_seen():
    """Twenty-three animals, twenty-three dots, none under another.

    The layout this replaced spread the animals with `p.x.invert(centre +
    offset)`, and a band scale inverts to the nearest *category*: every offset
    came back as the tick, the whole cohort was drawn on one line, and nine
    pairs of animals sat closer together than a dot is wide. Nothing caught it
    because the panel still lints clean -- overlapping marks are not a
    diagnostic -- so the guard has to be this: measure the dots on the page.
    """
    from inklet.core import resolve
    from inklet.draw.coords import as_drawn
    from inklet.draw.shapes import MARK_KIND

    boxes = [placed.bbox
             for placed in resolve(as_drawn(mouse.panel_e(29.0, height=34.0)
                                            .build())).values()
             if placed.diagram.kind == MARK_KIND]
    centres = [((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2) for b in boxes]
    size = boxes[0].x1 - boxes[0].x0

    assert len(boxes) == sum(data.COHORT.values())
    assert all(abs((b.x1 - b.x0) - size) < 1e-9 for b in boxes)
    closest = min(((a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2) ** 0.5
                  for i, a in enumerate(centres) for c in centres[i + 1:])
    assert closest >= size - 1e-9
