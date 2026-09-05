"""The case inklet has no answer for yet: a graph, not a flow.

Every layout so far has been a tree the author placed by hand through stacks.
This is a bipartite fan plus some skip connections -- the shape where a real
graph layout engine (ELK, dagre) earns its keep. Rendering it honestly shows
exactly where M1 stops.
"""
import dataclasses
import inklet

TH = inklet.use_theme(dataclasses.replace(inklet.theme("nature"), font_family="Noto Sans"))

SRC = ["retina", "LGN", "V1", "V2", "MT"]
DST = ["parietal", "temporal", "frontal", "SC"]

left = [inklet.box(n, width=18) for n in SRC]
right = [inklet.box(n, width=20) for n in DST]

fig = inklet.figure(width=inklet.COLUMN_DOUBLE)
fig.add(inklet.hstack([inklet.vstack(left, gap=5),
                    inklet.spacer(70, 1),
                    inklet.vstack(right, gap=7)], gap=6))

# A dense, deliberately tangled connectivity matrix.
EDGES = [(0,0),(0,1),(1,0),(1,2),(1,3),(2,0),(2,1),(2,2),
         (3,1),(3,2),(3,3),(4,0),(4,2),(4,3)]
for a, b in EDGES:
    fig.link(left[a], right[b])
# and some skip connections inside the left column, which must cross the fan.
# Straight or elbowed they drive through the boxes between their endpoints;
# route="avoid" is what makes them go round.
fig.link(left[0], left[3], route="avoid")
fig.link(left[1], left[4], route="avoid")

fig.save("stress/dense_graph.svg")
print(fig.report())
