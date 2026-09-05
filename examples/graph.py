"""A 28-node RNA-seq pipeline nobody placed by hand.

Every coordinate in this figure comes from `inklet.graph`. The script says which
step feeds which; the layered layout decides the ranks, the order within each
rank, the corridors the long edges run down, and the millimetres.
"""

import inklet

inklet.use_theme("nature")

# The steps, keyed so the edge list reads like a description of the pipeline.
STEPS = {
    "fastq":   "raw reads\n(FASTQ)",
    "sheet":   "sample sheet",
    "genome":  "GRCh38",
    "gtf":     "GENCODE v44",
    "sets":    "MSigDB\nhallmarks",
    "qc":      "read QC",
    "trim":    "adapter trim",
    "index":   "genome index",
    "align":   "STAR align",
    "dedup":   "mark duplicates",
    "counts":  "featureCounts",
    "matrix":  "count matrix",
    "filter":  "expression filter",
    "norm":    "TMM normalise",
    "vst":     "variance\nstabilise",
    "pca":     "PCA",
    "corr":    "sample\ncorrelation",
    "batch":   "batch check",
    "de":      "DESeq2 fit",
    "shrink":  "LFC shrink",
    "call":    "call DE genes",
    "gsea":    "GSEA",
    "string":  "STRING network",
    "volcano": "volcano plot",
    "heat":    "heatmap",
    "table":   "results table",
    "panels":  "figure panels",
    "report":  "report",
}

EDGES = [
    ("fastq", "qc"), ("qc", "trim"), ("trim", "align"),
    ("genome", "index"), ("index", "align"),
    ("align", "dedup"), ("dedup", "counts"), ("gtf", "counts"),
    ("counts", "matrix"), ("matrix", "filter"), ("sheet", "filter"),
    ("filter", "norm"), ("norm", "vst"), ("norm", "de"), ("sheet", "de"),
    ("vst", "pca"), ("vst", "corr"), ("pca", "batch"), ("corr", "batch"),
    ("de", "shrink"), ("shrink", "call"),
    ("call", "gsea"), ("sets", "gsea"), ("gsea", "string"),
    ("call", "volcano"), ("vst", "heat"), ("call", "table"),
    ("volcano", "panels"), ("heat", "panels"), ("string", "panels"),
    ("batch", "panels"),
    ("panels", "report"), ("table", "report"),
]

# A fixed box width keeps the ranks tidy; the layout takes the real sizes from
# the boxes either way, so unequal ones would work too.
boxes = {key: inklet.box(text, width=15) for key, text in STEPS.items()}

# `lane` is the width of a corridor reserved for an edge that skips ranks --
# four of them run down this figure. Widening it from the default pulls the
# long edges apart where they leave `call DE genes`.
pipeline = inklet.graph(boxes, EDGES, direction="down", rank_gap=5, lane=4)

fig = inklet.figure(width=inklet.COLUMN_SINGLE, theme="nature")
pipeline.add_to(fig)          # adds the diagram, then links every edge

# The graph wrapped the very boxes it was given, so the handles still work --
# `pipeline["call"]` and `boxes["call"]` are one object, and an annotation or an
# extra link can still be aimed at it.
assert pipeline["call"] is boxes["call"]

print("%d nodes, %d edges, %.1f x %.1f mm"
      % (len(boxes), len(EDGES), pipeline.width, pipeline.height))
print(fig.report())
fig.save("examples/graph.svg")
