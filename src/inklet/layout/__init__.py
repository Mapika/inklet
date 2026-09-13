"""Layout combinators. Give them diagrams, get back one diagram with everything
in the right place -- no coordinates typed by hand anywhere.
"""

from .annotations import FigureAnnotation, place_annotations
from .fit import fit
from .mosaic import PanelSpec, panel_mosaic
from .clear_space import place_in_clear_space
from .label_column import label_column
from .flow import (
    BOX_PAD, align_to, beside, box, flow, frame, grid, hstack, overlay, pad,
    spacer,
    stack, vstack,
)
from .graph import DIRECTIONS, LAYOUTS, Graph, GraphEdge, GraphError, graph
from .sankey import (
    ORDERS, Sankey, SankeyError, SankeyFlow, SankeyNode, sankey,
)
from .labels import (
    DEFAULT_RADII, LabelChoice, LabelWeights, label_plan, place_labels,
)

__all__ = [
    "FigureAnnotation", "place_annotations",
    "PanelSpec", "panel_mosaic", "place_in_clear_space", "label_column", "hstack", "vstack", "stack", "grid", "flow", "overlay",
    "pad", "frame", "box", "align_to", "spacer", "beside", "fit",
    "BOX_PAD",
    "graph", "Graph", "GraphEdge", "GraphError", "LAYOUTS", "DIRECTIONS",
    "sankey", "Sankey", "SankeyError", "SankeyFlow", "SankeyNode", "ORDERS",
    "place_labels", "label_plan", "LabelChoice", "LabelWeights",
    "DEFAULT_RADII",
]
