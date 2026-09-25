---
layout: section
title: Diagrams
description: Measured modules, routed connections and diagrams that share a page with plots.
groups:
  - title: Draw a diagram
    cards:
      - title: Measured connections
        page: diagrams.md
        image: assets/guides/diagrams-1.png
        text: Modules sized from their text, named ports, orthogonal and straight routes, and graph layout.
      - title: Component library
        page: diagram-components.md
        image: assets/guides/diagram-components-1.png
        text: Scientific symbols arranged in stacks and grids and connected through named anchors.
      - title: A methods diagram
        page: example-library.md#methods-flow
        image: gallery/process.png
        text: A complete methods flow from the example scripts.
      - title: Routing and label placement
        page: diagram-engine.md
        image: gallery/diagram-review.png
        text: Wrapped module text, connector labels that avoid one another, and obstacle routing in larger diagrams.
  - title: Diagrams with plots
    text: A diagram is a component like a plot, so both can be cells of the same document and share its preset.
    cards:
      - title: Circuit beside twelve plots
        page: dense-figures.md
        image: gallery/dense-figure.png
        text: Panel a of the dense figure page is a routed circuit diagram built with composition() and link().
      - title: Method diagram beside results
        page: composition-recipes.md
        image: assets/guides/composition-recipes.png
        text: A composition with named slots for a diagram, plots and a caption, reused with different content.
      - title: Diagram objects linked to measurements
        page: project-workflows.md
        image: assets/guides/project-workflow.png
        text: Diagram objects keep their IDs when the plotted measurements are replaced.
        tag: Experimental
---
# Diagrams

Inklet draws diagrams from modules whose size is measured from their text,
and from connections routed between named ports. Positions can depend on the
measured size of other components, so a diagram keeps its spacing when a
label changes. A diagram is placed in a document cell in the same way as a
plot, so a methods schematic and its results can share one page, one preset
and one set of panel letters.

<!-- cards -->

## Where to start

Read [measured connections](diagrams.md) for `composition()`, modules, ports
and routes. `fig.lint()` includes rules for connectors: a link that crosses a
shape it was not routed to (`LINK_CROSSES`), two crossing links
(`LINK_CROSSES_LINK`), an arrow whose end misses its target (`LINK_UNCLIPPED`)
and a label drawn over its own link (`LABEL_COVERS_SHAFT`). See the
[diagnostic codes](api.md#diagnostic-codes).
