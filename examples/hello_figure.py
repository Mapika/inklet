"""M1 acceptance test: fifteen lines, no coordinates, a figure that holds up.

If this script produces a clean SVG with zero lint diagnostics, the thesis is
proven -- boxes fit their text, the stack spaces itself, and the arrows land on
the boundaries of what they point at without anyone having said where anything is.
"""

import inklet

inklet.use_theme("nature")

sensor = inklet.box("Two-photon\nimaging")
extract = inklet.box("ROI extraction")
deconv = inklet.box("Spike deconvolution")
model = inklet.box("Encoding model")

pipeline = inklet.vstack([sensor, extract, deconv, model], gap=6)

fig = inklet.figure(width="89mm")
fig.add(pipeline)
fig.link(sensor, extract)
fig.link(extract, deconv, label="dF/F")
fig.link(deconv, model, label="rates")

report = fig.report()
print(report)
fig.save("examples/hello_figure.svg")

box = pipeline.bbox
print(f"figure content: {box.width:.1f} x {box.height:.1f} mm")
