"""A deliberately punishing figure: dense two-column methods panel.

Everything here is chosen to hurt -- rotated axis labels inside stacks, a real
grid with per-column widths, wrapped prose at a narrow measure, Greek and
subscripts, branch-and-merge links that cross, and panel letters that must hang
outside their panels without disturbing the layout.
"""
import inklet
from inklet import pt
from inklet.themes.color import mix

import dataclasses
# Name a family that is actually installed, so the report is about layout
# rather than 38 repetitions of "Helvetica Neue is not here".
TH = inklet.use_theme(dataclasses.replace(inklet.theme("nature"), font_family="Noto Sans"))
C = TH.color

def lettered(letter, panel):
    """Panel letter hanging top-left, outside the panel's own box."""
    tag = inklet.text(letter, size=TH.font_size_large, font_weight="bold")
    return inklet.hstack([tag, panel], gap=1.5, align="top")

def vlabel(s, **kw):
    return inklet.text(s, size=TH.font_size_small, **kw).rotated(-90)

def swatch(color, name):
    chip = inklet.box(inklet.spacer(3.2, 2.0), pad=0, radius=0.4,
                   fill=color, stroke="none")
    return inklet.hstack([chip, inklet.label(name)], gap=1.2, align="center")


# -- a: the rig -----------------------------------------------------------

laser  = inklet.box("Ti:Sapphire\n920 nm", fill=C(0))
eom    = inklet.box("EOM")
scan   = inklet.box("Resonant\nscan head")
obj    = inklet.box("16× 0.8 NA\nobjective", fill=C(1))
# A real raster, cut out and traced: it packs on its silhouette and arrows
# clip to the animal rather than to the picture frame.
photo  = inklet.asset("stress/assets/mouse.png", width=34, name="mouse")
mouse  = inklet.vstack([photo, inklet.label("head-fixed mouse")], gap=1.5)
pmt    = inklet.box("GaAsP\nPMT", fill=C(2))

beam = inklet.vstack([laser, eom, scan, obj, mouse], gap=4.5)
# A bracket, not a bare rotated word in the next column. "beam path" names the
# whole column from the laser to the animal, and stacked beside it the word
# only ever said "somewhere to my right"; the bracket's ticks say where the
# run starts and where it stops. `within=beam` because the two ends are
# nested inside that stack, and `place` puts the result back in the stack's
# own coordinates, which is the frame `bracket` drew it in.
spine = inklet.bracket(laser, mouse, side="w", within=beam,
                    text=vlabel("beam path"), clear=1.4, tick=1.2)
column = inklet.place([beam, spine])
rig  = inklet.hstack([column, inklet.vstack([inklet.spacer(1, 26), pmt])],
                  gap=2.0, align="center")
panel_a = lettered("a", rig)


# -- b: the pipeline ------------------------------------------------------

raw    = inklet.box("raw movie\n512 × 512 × 30 Hz")
motion = inklet.box("motion\ncorrection")
seg    = inklet.box("ROI\nsegmentation", fill=C(3))
neuro  = inklet.box("neuropil\nmask", fill=C(4))
dff    = inklet.box("ΔF/F₀")
decon  = inklet.box("deconvolution\n(OASIS)", fill=C(5))
spikes = inklet.box("spike trains")

branch = inklet.hstack([seg, neuro], gap=5)
flow   = inklet.vstack([raw, motion, branch, dff, decon, spikes], gap=5.5)
panel_b = lettered("b", flow)


# -- c: the response matrix ----------------------------------------------

ROWS = ["V1", "LM", "AL", "PM", "RL"]
COLS = ["0°", "45°", "90°", "135°", "180°", "225°"]
cells = []
for r, _ in enumerate(ROWS):
    for c, _ in enumerate(COLS):
        v = ((r * 7 + c * 3) % 9) / 8.0          # deterministic stand-in data
        cells.append(inklet.box(inklet.spacer(5.0, 3.6), pad=0, radius=0.3,
                             fill=mix(TH.paper, C(5), v), stroke="none"))
matrix = inklet.grid(cells, cols=len(COLS), gap=0.6)
col_hdr = inklet.hstack([inklet.label(c, size=pt(5)) for c in COLS], gap=1.9)
row_hdr = inklet.vstack([inklet.label(r, size=pt(5)) for r in ROWS], gap=2.1)
body    = inklet.hstack([row_hdr, inklet.vstack([col_hdr, matrix], gap=1.0, align="right")],
                     gap=1.4, align="bottom")
mat = inklet.hstack([vlabel("visual area"), body], gap=1.5, align="center")
panel_c = lettered("c", inklet.vstack([mat, inklet.label("drifting-grating direction")], gap=1.2))


# -- d: legend and caption ------------------------------------------------

legend = inklet.vstack([swatch(C(3), "segmented ROI"),
                     swatch(C(4), "neuropil annulus"),
                     swatch(C(5), "inferred spikes")], gap=1.4, align="left")
caption = inklet.text(
    "Two-photon calcium imaging of visual cortex. Fluorescence was corrected "
    "for neuropil contamination using an annulus of radius 20 µm, then "
    "normalised to a rolling 10th-percentile baseline F₀ before deconvolution.",
    size=TH.font_size_small, align="left", width=64)
panel_d = lettered("d", inklet.vstack([legend, caption], gap=3.0, align="left"))


# -- assembly -------------------------------------------------------------

fig = inklet.figure(width=inklet.COLUMN_DOUBLE, theme=TH)
# A grid, not nested stacks: two hstacks share no column geometry, so panel b
# and panel d would start at different x and the letters would not line up.
fig.add(inklet.grid([panel_a, panel_b, panel_c, panel_d], cols=2,
                 col_gap=10, row_gap=9, align="start", valign="start"))

fig.link(laser, eom); fig.link(eom, scan); fig.link(scan, obj)
fig.link(obj, photo, label="excitation")
fig.link(photo, pmt, label="emission", route="orthogonal")

fig.link(raw, motion); fig.link(motion, seg); fig.link(motion, neuro)
fig.link(seg, dff); fig.link(neuro, dff, label="subtract")
fig.link(dff, decon); fig.link(decon, spikes)

fig.save("stress/hard_figure.svg")
print(fig.report())
root, places = fig.build()
print(f"nodes={len(list(root.walk()))}  placements={len(places)}  "
      f"page={fig.page_rect(root.bbox).width:.1f}x{fig.page_rect(root.bbox).height:.1f}mm")
