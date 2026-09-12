# Local layout editor

Available since **4.0.0.dev8**, with the redesigned studio workspace in
**4.0.0.dev12**, under `inklet.experimental.layout_editor`. Arrange named
content, edit labels and appearance, and review the actual Python-compiled
figure. Downloaded SVG/PDF files use that same successful preview.

![Inklet studio with object navigation, a large figure canvas and focused style controls](assets/guides/editor-studio.png)

The [complete example](../examples/layout_editor.py) opens the reusable report
from [composition recipes](composition-recipes.md). From the checkout, run:

```sh
python examples/layout_editor.py
```

Open the local URL printed in the terminal. Keep that Python process running;
press Ctrl+C to stop it. This is a local editor, not a standalone HTML editing
file. Ordinary [figure viewers](compiled-viewer.md) remain available for
sharing a finished document without a Python process.

## A workspace for your figure

The desktop workspace has a searchable object navigator, a central canvas and
an inspector with **Layout**, **Labels** and **Styles** tabs. Select an object
from the navigator or directly on the figure. Nested objects retain their
hierarchy, and the inspector shows the exact source path. On smaller screens,
a **Content** selector replaces the navigator; on phones the inspector sits
below the canvas.

Use **+**, **−** and **Fit** to explore the figure. The zoom percentage is
relative to the fitted view, not a physical-size preview. Ctrl/Cmd + wheel also
zooms. Use the pan tool, middle-button dragging, or hold Space and drag to move
the viewport. View changes never resize the authored figure or enter its undo
history. Object movements and corner scaling still use figure coordinates at
any zoom level.

Changed fields are highlighted and counted. Switch inspector tabs to combine
edits, then **Apply changes** as one undo step. **Discard** clears unapplied
fields. Selecting another object, refreshing, undoing, opening a file, saving
or exporting asks you to apply or discard pending changes first; browser
navigation also warns about pending edits. Applied changes still need **Save
choices** to download a portable file.

Colour swatches open the native picker, while the adjacent field accepts exact
colour values. Automatic/transparent values use a muted swatch. Undo/redo and
file actions stay in the header; **Export** offers SVG and PDF. The footer shows
compile feedback and the current revision. The **Shortcuts** dialog documents
all controls, including Ctrl/Cmd + Enter to apply, Ctrl/Cmd + Z to undo,
Ctrl/Cmd + Shift + Z to redo and Ctrl/Cmd + S to save applied choices. Text inputs
retain native text undo.

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

Select a composition child, choose the **Labels** tab, then change its fields and choose **Apply
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

## Edit appearance alongside layout

![Named line and marker styles edited in the composition inspector](assets/guides/layout-editor-styles.png)

Choose the **Styles** tab. Layout, Labels and Styles retain their pending
changes when switching sections; **Apply changes** compiles them together as
one undo step. Apply or discard pending fields before selecting another content target.

| Named content | Available appearance controls |
| --- | --- |
| Keyed plot `line` instructions | Stroke colour, physical line width, opacity |
| Keyed plot `scatter` instructions | Constant colour and diameter, opacity |
| Text components and string module captions | Fill colour and physical text size |
| Module boxes | Fill, stroke colour and physical line width |
| Keyed plot `text`/`annotate` and named composition callouts | Fill colour and physical text size |

Colours accept the colour parser's hex, RGB and named CSS forms; `none` also
works for fill and stroke. Opacity ranges from 0 to 1. Widths use millimetres;
marker size is **diameter**, and text size must be positive. Blank style fields
remove an explicit keyword and use the renderer's automatic/preset behaviour.
That removal is saved as JSON `null`. **Reset target** instead restores the
current source's layout, labels and styles together. Parent artwork scaling
still scales the resulting text and strokes.

```python
editor.command('edit', {
    'path': '/caption',
    'placement': {'x': 18},
    'labels': {'label': {'kind': 'module-label', 'text': 'Reviewed response'}},
    'styles': {
        'text': {'kind': 'module-text', 'size': 4, 'fill': '#203e53'},
        'box': {'kind': 'module-box', 'fill': '#e9f0f4', 'stroke_width': 0.4},
    },
})
```

Larger text is remeasured, so connected modules and dependent layout update.
Style edits retain live data, named instruction keys and unedited source choices.
Data-driven marker colour/diameter controls are omitted, including ramped
colours. If a source revision turns an edited constant into a data mapping,
the saved style is reported as incompatible, such as `/chart#style:samples`.
Explicit discard removes that style target's edits while preserving compatible
labels and placements on the chart.

Styles use the same named path, key and kind contracts as labels. New saved
files use schema 0.4; 0.1, 0.2 and 0.3 files still load. This unifies authoring
within the composition editor. The separate [linked-table style inspector](visual-editing.md)
retains its own source-bound format; its files are not interchangeable. Plot
titles, axes, bars, arbitrary factories, gradients and camera/material settings
are outside this style-control subset.

## Edit and review

Choose a named path in **Content** and an inspector tab, enter the fields you want to change, then
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

**Undo** and **Redo** retain up to 100 successful authoring edits. A new edit after
undo starts a new history branch. Shared nested definitions remain shared:
editing or resetting one occurrence affects the same definition wherever it
appears. Distinct placements of that shared content remain independently editable.

## Save, reopen and export

**Save choices** downloads the versioned JSON described in
[saved layout choices](layout-overrides.md). **Open** loads that
same format. The file contains changed layout, label and supported style fields.
Other source content, assets and undo history stay outside the file. Keep it alongside the recipe.

**Export → SVG** and **Export → PDF** export the successful preview revision.
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
