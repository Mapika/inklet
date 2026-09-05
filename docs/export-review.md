# Export and review

Compile a document once and use the resulting snapshot for all exports.
Changing the authoring objects afterwards does not change that snapshot.

## Save vectors

```python
import inklet as i

doc = i.publication('single-column').document()
doc.add('message', i.component(i.text, 'A reproducible export'))
figure = doc.compile()
figure.save('figure.svg', 'figure.pdf')
assert figure.to_pdf().startswith(b'%PDF')
```

SVG/PDF saving needs the core package and fonts; it does not require Chrome,
Poppler or Pillow unless the figure itself contains image-dependent content.
Both backends consume the same resolved geometry. Independent viewers can
still differ in antialiasing, text rendering and raster interpolation.

## Text and physical size

Document exports default to embedded, searchable text. `text='outline'`
converts glyphs to paths. A publication profile can set the default text mode;
an explicit save/export argument takes precedence.

```python
figure.save('outlined.svg', 'outlined.pdf', text='outline')
assert '<svg' in figure.to_svg(text='outline')
```

Legacy `Figure.save()` retains its existing outlined-text default, while
`Figure.export()` defaults to embedded text. Set `text=` explicitly when
mixing APIs and needing one text policy.

Page dimensions are physical millimetres. Preview DPI changes the PNG pixel
dimensions, not the page width, vector detail or source-image resolution.
Profiles such as `publication('double-column', dpi=300)` combine export
defaults with print thresholds. They are general presets; verify the destination's
requirements yourself.

## A review bundle

With the [preview dependencies](installation.md#visual-review) installed:

<!-- Requires preview renderers. -->

```python
paths = figure.export('out/review', name='experiment', dpi=150)
print(paths['review'])
assert paths['review'].is_file()
```

Open the HTML file locally, or use [watch mode](cli.md#watch-and-preview).

| Output | Contents |
|---|---|
| `experiment.svg`, `experiment.pdf` | Vector exports |
| `experiment.png` | Chrome/Chromium rendering of the SVG |
| `experiment-pdf.png` | Independent Poppler rendering of the PDF |
| `experiment.html` | Review page with downloads, filters and SVG highlights |
| `experiment-diagnostics.txt`, `experiment-diagnostics.json` | Findings with codes, severity, geometry and targets |
| `experiment-manifest.json` | Dimensions, export settings, files and document metadata |

For documents, metadata includes dataset revisions and hashes, source records,
font hashes, named cell bounds, compilation statistics and publication settings.
Different base names let several figures share an output directory.

Pass `compare_pdf=False` to omit the PDF PNG preview; the PDF file is still
written. All rendering and comparison work completes before existing bundle
files are replaced, so a rendering failure retains the previous successful
bundle. Replacement consists of individual file operations, not a filesystem
transaction covering the directory.

## Inspect diagnostics

```python
errors = [finding for finding in figure.diagnostics if finding.severity == 'error']
assert not errors, figure.report()
```

The review page filters findings by component, severity and search text.
Clicking a spatial finding opens the vector view and highlights its location.
Parent component filters include nested children. Keep informational findings
visible and decide whether they are intentional in this figure.

`build` reports compilation/export success separately from findings. If your
workflow should reject warnings, implement that policy using their severity.
See [troubleshooting](troubleshooting.md#common-diagnostics) and the
[diagnostic reference](api.md#diagnostic-codes).

## Compare revisions

<!-- Requires preview renderers. -->

```python
doc.replace('message', i.component(i.text, 'The revised export'))
revised = doc.compile()
comparison = revised.export('out/revised', name='experiment', dpi=150,
                             compare_to=paths['manifest'])
assert comparison['review'].is_file()
```

The previous manifest path or its containing directory is accepted. A directory
must contain `<name>-manifest.json`. The new bundle includes copies of the
previous PNG and manifest so it can be reviewed independently.

Matching physical dimensions, DPI and image dimensions enable an opacity slider
and amplified difference image. A change fraction counts pixels differing by
more than 25/255 in any RGB channel. It is a visual change measure, not a
scientific accuracy score. Different dimensions are displayed side by side
without resampling or a pixel score.

CLI equivalent:

```sh
inklet build first_figure.py --output out/second --name experiment \
  --compare-to out/first/experiment-manifest.json
```

This assumes the first bundle already exists. Watch mode compares successive
successful builds automatically unless you specify a fixed reference.

## Automated visual checks

```sh
python tools/visual_check.py --output out/visual
```

The report shows baseline, current and amplified difference images for SVG and
PDF fixtures. Follow [the visual test instructions](../tests/visual/README.md)
before accepting a baseline. The [stress test](stress20.md) additionally checks
large mixed-content figures, live edits and physical resizing.
