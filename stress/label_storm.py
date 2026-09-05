"""Thirty-four labels in a field with room for about twelve.

The case `inklet.annotate` alone cannot win. Every label is placed the instant it
is asked for, against the labels already down and nothing else, so the first
few get the side they asked for, the middle ones get shoved round the compass,
and the last ones land wherever is least bad -- on the dots, on each other, and
with leaders crossing half the field. `fig.lint()` says so in `CROWDING` and
`OVERLAP`, and until `inklet.place_labels` there was nothing to do about it but
move them by hand.

Run it and it prints both lints: the same tree before and after the placer.

    .venv/bin/python stress/label_storm.py

Points are a fixed table rather than a seeded generator, because a stress case
whose geometry can drift is not a regression test.
"""
import dataclasses

import inklet

TH = inklet.use_theme(dataclasses.replace(inklet.theme("nature"),
                                       font_family="Noto Sans"))

#: (x, y, gene) in millimetres, in a field about 88 x 55mm.
POINTS = [
    (66.3, 28.9, 'Sst'),
    (26.4, 24.0, 'Pvalb'),
    (66.6, 9.1, 'Vip'),
    (71.8, 40.6, 'Lamp5'),
    (39.4, 32.9, 'Sncg'),
    (23.1, 41.6, 'Calb1'),
    (41.1, 25.1, 'Calb2'),
    (36.9, 33.0, 'Npy'),
    (60.2, 3.3, 'Cck'),
    (82.2, 24.4, 'Reln'),
    (59.9, 30.3, 'Chat'),
    (82.5, 51.4, 'Th'),
    (13.2, 21.3, 'Gad1'),
    (43.2, 26.4, 'Gad2'),
    (45.8, 45.5, 'Slc17a7'),
    (49.6, 43.4, 'Rorb'),
    (80.4, 50.5, 'Foxp2'),
    (11.0, 5.6, 'Cux2'),
    (45.8, 37.1, 'Fezf2'),
    (73.8, 48.6, 'Ctip2'),
    (15.9, 16.5, 'Satb2'),
    (47.9, 28.0, 'Tbr1'),
    (22.2, 11.9, 'Pax6'),
    (58.4, 47.0, 'Dlx1'),
    (7.1, 52.1, 'Nkx2-1'),
    (35.2, 40.0, 'Lhx6'),
    (75.3, 47.9, 'Prox1'),
    (57.0, 23.0, 'Neurod6'),
    (15.9, 46.1, 'Cntnap2'),
    (14.3, 24.0, 'Grin2b'),
    (43.7, 31.5, 'Kcnq2'),
    (51.0, 27.4, 'Scn1a'),
    (54.2, 36.5, 'Syt1'),
    (80.9, 22.4, 'Snap25'),
]


def field() -> inklet.Diagram:
    """The dots on their own, each named so a label can find it."""
    return inklet.place([
        ((x, y), inklet.marker("circle", 1.3, fill=TH.color(0),
                            stroke="none").named(gene))
        for x, y, gene in POINTS
    ])


def labelled(dots: inklet.Diagram) -> inklet.Diagram:
    """One `annotate` per dot, all asking for north, chained as anyone would."""
    art = dots
    for _, _, gene in POINTS:
        art = inklet.annotate(dots.find(gene), gene, within=art, clear=1.2,
                           size=TH.font_size_small,
                           leader_style={"stroke_width": TH.hairline})
    return art


def sheet(art: inklet.Diagram, caption: str) -> inklet.Figure:
    fig = inklet.figure(width="104mm", theme=TH, margin=4)
    fig.add(inklet.vstack([art, inklet.text(caption, size=TH.font_size_small,
                                      text_fill=TH.muted)],
                       gap=TH.gap("l"), align="center"))
    return fig


def counted(fig: inklet.Figure) -> dict:
    counts: dict = {}
    for finding in fig.lint():
        counts[finding.code] = counts.get(finding.code, 0) + 1
    return counts


if __name__ == "__main__":
    dots = field()
    before = labelled(dots)
    after = inklet.place_labels(before)

    raw = sheet(before, "34 labels, placed one at a time")
    fixed = sheet(after, "the same 34, placed together by inklet.place_labels")
    print("before:", counted(raw))
    print("after: ", counted(fixed))
    fixed.save("stress/label_storm.svg")
