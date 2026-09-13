# Original scientific gallery

Two original native-vector plates: 15 panels on olfactory circuits and 17 panels
on community connectivity. No reference image, traced contour, manually read
paper value, or old figure coordinate is used to build these pages.

From this repository (or the unpacked source archive):

```bash
python -m pip install -e '.[render,images,three]'
python -m pip install -r examples/inspo/requirements.txt
python examples/inspo/fly_data.py --data out/fly-data
python examples/scientific_gallery/recreate.py --data out/fly-data --dpi 220
python examples/scientific_gallery/verify.py --data out/fly-data
```

Use Python 3.11 or newer. Public acquisition caches over a gigabyte of data and
can take several minutes. The gallery fetches 96 deterministic community
skeletons and four spatial-index shards if absent. The main acquisition adapter
also caches anatomy used by the earlier examples; the gallery reads only the
sources named in its manifest. No credentials are needed.

`--output` defaults to `out/scientific-gallery`; `--page olfactory` or
`--page communities` rebuilds one plate. SVG/PDF have editable, subset-embedded
fonts and no embedded raster images. PNG is a display preview. Full native
matrices are deliberately vector; the community SVG is larger than a typical
web illustration. The docs use the PNG preview and offer vectors as downloads.

- `dense.py`: named subplot factories and complete page layouts.
- `helpers.py`: common physical typography and shared anatomy styling.
- `data.py`: computations from released annotation tables, type weights and SWCs.
- `synapses.py`: deterministic annotation-record sampling from spatial shards.
- `verify.py`: checks against source skeletons and output geometry/metadata.
- `publish_assets.py`: prepares the local docs assets and source archive.

The library components are `panel_mosaic`, `anatomy_view`, `Graph.build`,
`label_column`, `value_table`, and `place_in_clear_space`. Use the smaller
examples in `docs/scientific-authoring.md` to start a new figure.

The source archive includes the working Inklet source snapshot, recipes,
derived measurements and provenance. It excludes cached public source datasets
and reference images. Install the included source snapshot to get these new
APIs; a previously installed Inklet release may not include them.

## What is measured

Olfactory anatomy uses the 60 cached cells in each of four ORN types, 12 cached
DA1_lPN cells and two MZ_lv2PN cells (254 total). These are deterministic display
subsets. The census independently counts all annotated cells from all 53 shared
ORN types. Connectivity uses released matched-type male weights. The target
matrix normalizes within its 18 displayed target types, not all output.

SWC branch nodes have more than one **valid** child; missing-parent sentinels
are excluded. Zero-branch cells remain zero on a symlog axis. Extents are
registered coordinate spans normalized within each arbor, not physical lengths.

The AL sample contains 756 spatial annotation records and 742 unique
coordinate/type tuples. We retain repeated coordinates and do not claim unique
presynaptic-site counts. Both confidences must be at least 0.5, the ROI must be
left AL, and the presynaptic type must match one of the four displayed ORN types.
Depth distributions weight records. They are not whole-AL synapse inventories.

Community weights aggregate released type edges over 311 disjoint memberships
(8,231 types). Ranks include self-links; graph links exclude them. Graph node
shapes indicate at most ten versus more than ten types. The class-composition
panel uses class or, when absent, superclass; each type gets one modal-category
vote. Reciprocity counts unordered community pairs, ordered by numeric ID.
Neighbor degrees exclude the diagonal. The pair-density colorbar counts pairs
per bin. These are descriptive examples, with no hypothesis tests or inferred
biological mechanism.

## Attribution

`provenance.json` retains pinned URLs, upstream hashes, body IDs, selections and
licenses. MaleCNS data are attributed to the released dataset under CC BY 4.0;
FlyWire annotations carry CC BY-NC 4.0. Template meshes and registration come
from the pinned navis-flybrains repository; retain its template attribution and
license notices. Inklet's MIT code license does not replace upstream licenses.
See `docs/scientific-gallery.md` for source links and interpretation limits.
