# Local layout editor

Available since **4.0.0.dev8**, with mouse gestures in **4.0.0.dev9** and named label editing in **4.0.0.dev10**, under `inklet.experimental.layout_editor`. Adjust
named placements and dimensions in a browser while Python recompiles the
actual composition. The preview and downloaded SVG/PDF come from the same
compiled figure, including plots, nested diagrams and native 3D content.

![Mouse selection and proportional scaling handles on a native 3D object](assets/guides/layout-editor-gestures.png)

The [complete example](../examples/layout_editor.py) opens the reusable report
from [composition recipes](composition-recipes.md). From the checkout, run:

```sh
python examples/layout_editor.py
```

Open the local URL printed in the terminal. Keep that Python process running;
press Ctrl+C to stop it. This is a local editor, not a standalone HTML editing
file. Ordinary [figure viewers](compiled-viewer.md) remain available for
sharing a finished document without a Python process.

## Start with your composition

```python
import inklet as i
from inklet.experimental.layout_editor import LayoutEditor

recipe = i.composition(120, 75)
recipe.add('chart', i.plot_spec(x=(0, 2), y=(0, 4)).line([(0, 1), (1, 2), (2, 3)]).axes(),
           x=13, y=8, anchor='area-nw', width=recipe.page_width - 26, height=30)
recipe.add('caption', i.module('Response'), x=13, y=55)
editor = LayoutEditor(recipe).start()
print(editor.url)
```

In a notebook or interactive Python session, leave the editor running while you
open its URL. It listens only on the local computer. `start(port=...)` can
request a particular port; the default chooses an available one. The editor
retains the supplied recipe as its live source and edits independent copies.
It does not rewrite Python or modify the source recipe.

Pass `preset='scientific.general'` or another preset name to compile under that
preset. By default, the containing document follows the composition's physical
width and height, including its coordinate unit. Optional `width=` and
`height=` arguments fix the containing document's dimensions in millimetres;
those dimensions remain authoritative when the authored page size changes.

## Move and scale with the mouse

Click a named object in the preview and drag it to move. Corner handles scale
its complete artwork proportionally, keeping the opposite corner fixed. This
works for plots, modules, text, images, native 3D components and nested
compositions. A dashed outline follows the pointer; release to compile the
result and update dependent links. Escape or a cancelled pointer gesture leaves
the figure unchanged. A simple click selects without making an edit.

Use Alt-click to select a containing group, or choose its path in **Content**.
Drag a selected group's outline to move the group. With the canvas focused,
arrow keys move the selected object by 1 mm in figure space; Shift changes that
to 10 mm. Mouse and pointer gestures use the same coordinates even inside
scaled groups or compositions with different coordinate units.

Each completed edit is one undo step. Movements add offsets to measured
positions instead of discarding their relationships. Repeated offsets are
combined, so a long editing session does not grow ever-deeper expressions.
Saved layout files retain movement and scaling for Python reconstruction.

**Scaling artwork also scales its text and strokes.** To resize a plot's data
region while retaining physical typography, use the width/height controls
below. The **Uniform scale** field gives an exact artwork scale factor; Reset
target restores the original factor and placement.

The selectable units are named composition children and groups. Individual
marks, ticks, axis labels and connector segments remain part of their owning
plot or diagram. Scaling and movement do not remove authored constraints or
top-fitting behavior; dependent content can reflow when the compiler rebuilds.

## Edit labels and callouts

![Editing a named plot callout with text, side, clearance and leader controls](assets/guides/layout-editor-labels.png)

Select a composition child, then edit its **Label** fields and choose **Apply
changes**. The editor supports text components created with `component(i.text,
...)`, string module captions, and plot `title`, `text` and `annotate`
instructions with an explicit string `key`. For composition callouts, supply a
unique `name` and select the composition that owns the callout.

```python
recipe['chart'].annotate(1, 2, 'Reference observation', key='observation', side='s', clear=4)
recipe.annotate('caption', 'Measured response', name='response-note', side='e', clear=3)
editor.command('refresh')
editor.command('edit', {
    'path': '/chart',
    'labels': {'observation': {'kind': 'plot-annotate', 'text': 'Reviewed observation', 'side': 'sw'}},
})
```

Callouts expose their preferred compass side, clearance in physical millimetres,
and leader visibility. Automatic placement can choose another side to avoid
conflicts. Plot clearance can be left blank to use its automatic value. This
increment edits callout content and placement preferences; it does not add free
mouse dragging of individual callouts or axis-label editing.

A label's identity is its composition path, explicit key and kind. For example,
`/chart` plus `observation` identifies a plot annotation even when its instruction
moves in the recipe. Replacing that key with a different instruction kind is an
incompatible target. A removed or incompatible label is reported as
`/chart#observation`; explicit discard drops that label's edits while retaining
compatible placement and label edits on the same chart. Renaming a path or key
changes its identity. Reusing the same key and kind declares the same label.

Text changes are measured by the Python compiler: longer module captions can
move dependent modules and reroute their connections. Unedited labels, data
coordinates, styling and other source choices remain live. Shared definitions
share label edits; use an independent recipe copy for independent captions.
Undo/redo, reset, saved JSON and SVG/PDF exports include the label edits.

## Edit and review

Choose a named path in **Content**, enter the fields you want to change, then
select **Apply changes**. Other fields retain their definitions.

- Child placement fields are X, Y, anchor, width, height and uniform scale. Numbers use the
  containing composition's coordinate unit. For plots, width and height describe
  the data region; changing them does not scale text or strokes.
- A field marked **Measured** still follows its layout expression. Entering a
  number replaces that expression with a fixed value. **Reset target** restores
  that target's source layout, including its measured expressions.
- Blank child width or height means to use the authored content size. A blank
  anchor preserves the local coordinate frame. Composition size fields must
  remain positive.
- Nested compositions also expose their authored dimensions, coordinate unit
  and top-fitting option. Registered ports and measured links reflow when the
  compiler rebuilds.

Failed layouts show an error beside the Apply controls. The last successful
preview, saved choices and undo history remain available. The inspector does
not automatically resolve overlap or add constraints: author the required
measured relationships and minimum sizes in the Python recipe.

**Undo** and **Redo** retain up to 100 successful layout edits. A new edit after
undo starts a new history branch. Shared nested definitions remain shared:
editing or resetting one occurrence affects the same definition wherever it
appears. Distinct placements of that shared content remain independently editable.

## Save, reopen and export

**Save layout** downloads the versioned JSON described in
[saved layout choices](layout-overrides.md). **Open layout choices** loads that
same format. The file contains changed placements and dimensions, not the
source content, styles, assets or undo history. Keep it alongside the recipe.

**Download SVG** and **Download PDF** export the successful preview revision.
If another editor tab changes the session first, stale commands and export
links are rejected. Use **Reload editor** to obtain the current shared state.

The same operations are available in Python:

```python
import json
from pathlib import Path

editor.command('edit', {'path': '/chart', 'placement': {'height': 35}})
editor.command('gesture', {'path': '/chart', 'dx': 2, 'dy': 1})
Path('layout-overrides.json').write_text(json.dumps(editor.overrides(), indent=2))
editor.figure.save('edited.svg', 'edited.pdf')
restored, report = recipe.with_layout_overrides(editor.overrides())
assert report['orphaned_targets'] == []
```

`editor.figure` is the last successful compiled snapshot and supports the normal
[export APIs](export-review.md), including PNG when render dependencies are
installed. `overrides()` and `snapshot()` return independently owned data.
Programmatic `command()` accepts `gesture`, `edit`, `reset`, `load`, `undo`,
`redo` and `refresh`; an optional `revision=` rejects stale callers. A gesture
uses figure-space `dx`/`dy` in millimetres. Optional `factor` and `corner`
(`nw`, `ne`, `sw`, `se`) scale from the opposite corner.

## Refresh changed source content

After updating a Dataset, module label or supplied component in the original
Python recipe, choose **Refresh source**. The editor reapplies saved layout
choices, recompiles and clears undo history. It does not watch or rerun Python
source files. Use a live Python session for source edits, or restart the example
and reopen its saved layout file after changing its script.

Removed named targets or measured references are reported as errors. The
**Refresh and discard removed targets** button appears after such a failure;
it explicitly discards incompatible entries and reports their paths. The last
successful figure remains visible until a refresh succeeds. Loading an
incompatible file also fails rather than silently dropping choices; reconcile
it explicitly through the Python [override API](layout-overrides.md) if needed.

```python
recipe['caption'].configure('Updated source label')
editor.command('refresh')
assert not editor.snapshot()['undo']
editor.close()
```

Closing the editor stops its server. Its compiled figure and saved choices
remain accessible in Python. The `with LayoutEditor(recipe) as editor:` form
starts and closes the server automatically; keep that context alive during
browser use.

The inspector edits named composition layout and artwork scale. Label content,
individual plot marks, camera controls, and file watching are not part of this interface.
The separate [linked-plot appearance editor](visual-editing.md) retains its
existing scope. Broader authoring and identity work remains on the
[4.0 roadmap](roadmap.md).
