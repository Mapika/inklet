"""Explicit review coverage for every subplot in the two reference pages."""
import json
from pathlib import Path
from layout import PANELS

REVIEW={'chemosensory': {'A': ('Fixed',
                        'Angular arrows and guessed label widths; overly flat anatomy; wrong Kenyon-cell subtype under the label.',
                        'Uses native curved arrows, measured tags, shaded meshes, depth-cued real paths, and actual KCab-s skeletons. '
                        'Camera/selection remains a reconstruction.'),
                  'B': ('Fixed; recomputed data',
                        'Malformed transcription had 67 category labels for 64 pairs and repeated names.',
                        'Replaced with 53 unique ORN type records joined across pinned MaleCNS/FlyWire annotations. Bilateral totals '
                        'include unknown sides; counts and ordering differ from the original paper selection.'),
                  'C': ('Fixed',
                        'The overview lost its long connections; the inset should localize only the left AL.',
                        'Restored full ORN skeletons over shaded overview tissue. The enlarged AL(L) still shows measured local '
                        'terminal sites, in one oblique camera.'),
                  'D': ('Fixed; data limitation',
                        'The rotated axis title crowded the tick labels.',
                        'Title clearance now uses measured tick and title extents. Heights are approximate reference readings; exact '
                        'published selections are not recovered.'),
                  'E': ('Fixed; source limitation',
                        'A separately fitted ghost brain implied registration with the close-up arbor.',
                        'Removed that overlay and unsupported DA1 label. Separate framed whole-brain locators use real registered '
                        'neurons. Male/female close-ups share one arbor frame; original DA1 ROI close-up is unrecovered.'),
                  'F': ('Fixed',
                        'Sparse color in LH; one female bar used the wrong color.',
                        'All observed colored target sites are retained in a denser real sample; gray background is subsampled '
                        'explicitly. Corrected the M_lvPNm45 female segment to blue. Reference bar values remain approximate.'),
                  'G': ('Fixed; approximate data',
                        'Printed r=.55 disagreed with displayed points; label boxes used guessed widths.',
                        'Pearson r=.28 and OLS line now come from displayed approximate coordinates. Measured tags and '
                        'boundary-connected leaders replace guessed boxes. Per-point biological encodings remain reference '
                        'approximations, not verified annotations.'),
                  'H': ('Fixed; data limitation',
                        'The remaining trace was labeled bootstrapped despite using approximate values.',
                        'Unsupported bootstrap claim removed, reference approximation labeled on chart and page. No original '
                        'bootstrap analysis is claimed.'),
                  'I': ('Fixed',
                        'Flat symmetric halves; missing anatomical regions; label did not name the actual displayed ascending '
                        'example.',
                        'Different detailed/schematic halves, brain and VNC regions, nerve outlines and curved arrows. Actual '
                        'AN09B017d and LgLG1a are now drawn under their labels.'),
                  'J': ('Fixed',
                        'Missing locators and inconsistent heading widths.',
                        'All six examples have anatomical locators; headings now use measured tags. Camera/subset choices remain '
                        'documented.'),
                  'K': ('Fixed; data limitation',
                        'Bar origin and lengths disagreed with the axis transform.',
                        'All endpoints use the same Inklet scales as the axis. Explicit 12.5% truncation note; values remain '
                        'approximate.'),
                  'L': ('Fixed; data limitation',
                        'Missing female VNC observations looked like zero and several type labels were mistranscribed.',
                        'Restored no-data annotation with null data values, negative-side tick, and corrected LgLG2/WG2/WG3 type '
                        'labels from the reference. Other values and mean guides remain approximate.'),
                  'M': ('Checked; source limitation',
                        'Ten downstream-partner anatomical views and their color scale.',
                        'Measured group headings and separate dimorphic/isomorphic labels retained. These are recomputed top '
                        'partners; original selections are not recovered.')},
 'dimorphism': {'A': ('Fixed; analysis difference',
                      'Verdict-based noise percentages appeared to describe a fixed weight threshold.',
                      'Removed the unsupported threshold divider; percentages explicitly describe noise/non-noise release verdicts. '
                      'Endpoint percentages describe displayed cumulative arrays.'),
                'B': ('Checked; source limitation',
                      'Registered male/female vpoEN in two projections.',
                      'Both full connection views and their locators retained. Hemisphere convention and camera differences remain '
                      'documented.'),
                'C': ('Fixed',
                      'Letters were too high inside circles; sex headings were not centered on columns.',
                      'Visible glyph bounds now center s/i/d at their circle centers and sex symbols over each column. Zero-weight '
                      'edge remains dashed.'),
                'D': ('Fixed; reference example',
                      'Headers and values sat high in cells; transformation labels conflicted with arrows.',
                      'Visible glyph bounds center headers/numbers in their cells. Sex headings center on both tables; shared '
                      'operation labels sit between arrows and FDR text above its arrow. Numerical values remain reference '
                      'transcriptions.'),
                'E': ('Fixed',
                      'Fixed textboxes and manually specified endpoints were fragile.',
                      'Measured native tags and boundary-attached connectors now draw the decision diagram. Requested routing '
                      'waypoints remain explicit.'),
                'F': ('Checked; data limitation',
                      'Four worked-example input/output bars.',
                      'Stack order, sex labels and key checked. Values remain approximate reference readings.'),
                'G': ('Fixed; sampled data',
                      'Title said all connections while display omitted zero weights.',
                      'Labeled stratified sample: up to 36,000 positive pairs and 2,000 per zero-weight direction. Explicit zero '
                      'gutters, separate from positive log domain. FDR colors retained; not a full-density plot.'),
                'H': ('Fixed; analysis difference',
                      'Legend text overlapped curves and its keys were scattered.',
                      'One measured, boxed legend now groups population colors and line styles in open plot space. Segment-level '
                      'checks require clearance from every curve. Population definitions and recomputed marginals are retained.'),
                'I': ('Checked',
                      'Connection-count pies and noise-removed stacks.',
                      'Rounded labels, sector sums and connectors checked. Counts are the printed reference percentages.'),
                'J': ('Checked',
                      'Synapse-count pies and noise-removed stacks.',
                      'Rounded labels and sectors checked. Female printed percentages sum to 100.1%; geometry uses the remainder as '
                      'documented.'),
                'K': ('Fixed; source limitation',
                      'Male/female color labels were reversed.',
                      'Independent +1 male / 0 / −1 female labels derive from the same signed scale. Male-location proxy is '
                      'explicitly labeled; original spatial-density analysis remains unrecovered.'),
                'L': ('Fixed; source limitation',
                      'Labels used arbitrary y positions, and illustrated partitions were not nested.',
                      'Band targets now derive from actual cumulative community sizes. Measured label column supplies leaders and '
                      'clearance. Intermediate illustrative partitions now nest, but remain explicitly non-inferred.'),
                'M': ('Fixed; analysis difference',
                      'Selection rectangle mismatched the zoom slice; adjacent labels overlapped; other class was absent.',
                      'Shared Panel.region transform determines zoom source box. Measured column labels attach to cell centers, both '
                      'views share opacity normalization, and other is included in the legend. Matrix remains a community aggregate.'),
                'N': ('Checked',
                      'Twelve enriched-cluster bars and two totals.',
                      'Exact released counts, row order and total proportions checked. Narrow segments can omit internal numeric '
                      'labels to preserve legibility.'),
                'O': ('Fixed; analysis difference',
                      'Node rectangles hid heads; edge classes and variable sizes were ambiguous.',
                      'Native connect clips curved edges to node boundaries with standoff and opposing bows. Nodes now have equal '
                      'size. Legend states >15% dimorphic aggregate-weight threshold and top-80 selection.'),
                'P': ('Refined; source limitation',
                      'Broad blue overdraw hid arbor structure.',
                      'Reduced width and opacity while retaining all 255 released members. Camera and overlap still differ from the '
                      'reference.'),
                'Q': ('Checked; data limitation',
                      'Two gene-expression proportion bars and four labels.',
                      'Stacks fill the common 0–1 scale; label colors match the segments. Proportions remain approximate manual '
                      'readings.')}}

def write(out):
    assert {page:set(rows) for page,rows in REVIEW.items()}=={page:{k for k,_ in panels} for page,panels in PANELS.items()}
    assert sum(map(len,REVIEW.values()))==30
    text=['# Subplot-by-subplot review','',
          'All 30 panels were reviewed against the supplied references and the generated full-size pages. Updated after the independent audit and repair pass. “Checked” means no additional drawing defect was established; it does not certify equivalence to the original scientific analysis.','',
          'The current builder never reads reference JPEGs. Native Inklet changes provide measured tags, curved arrows, shared mesh/path/point cameras and optional surface display simplification, immediate boundary-aware connectors, measured label columns, and shared data-region transforms. See audit-resolutions.md for independent rechecks.','']
    for page,rows in REVIEW.items():
        text.extend(['## '+page,'','| Panel | Status | Finding | Resolution / remaining difference |','|---|---|---|---|'])
        text.extend(f'| {k} | {status} | {finding} | {resolution} |' for k,(status,finding,resolution) in rows.items())
        text.append('')
    (out/'panel-review.md').write_text('\n'.join(text)+'\n')
    (out/'panel-review.json').write_text(json.dumps(REVIEW,indent=2))
