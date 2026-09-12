# Local layout editor

Available in **4.0.0.dev8**, under `inklet.experimental.layout_editor`. Adjust
named placements and dimensions in a browser while Python recompiles the
actual composition. The preview and downloaded SVG/PDF come from the same
compiled figure, including plots, nested diagrams and native 3D content.

![The local layout inspector editing a mixed-content report](assets/guides/layout-editor.png)

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

## Edit and review

Choose a named path in **Content**, enter the fields you want to change, then
select **Apply layout**. Other fields retain their definitions.

- Child placement fields are X, Y, anchor, width and height. Numbers use the
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
Path('layout-overrides.json').write_text(json.dumps(editor.overrides(), indent=2))
editor.figure.save('edited.svg', 'edited.pdf')
restored, report = recipe.with_layout_overrides(editor.overrides())
assert report['orphaned_targets'] == []
```

`editor.figure` is the last successful compiled snapshot and supports the normal
[export APIs](export-review.md), including PNG when render dependencies are
installed. `overrides()` and `snapshot()` return independently owned data.
Programmatic `command()` accepts `edit`, `reset`, `load`, `undo`, `redo` and
`refresh`; an optional `revision=` rejects stale callers.

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

This first inspector edits composition layout. Drag handles, label content,
plot styling, camera controls, and file watching are not part of this interface.
The separate [linked-plot appearance editor](visual-editing.md) retains its
existing scope. Broader authoring and identity work remains on the
[4.0 roadmap](roadmap.md).
