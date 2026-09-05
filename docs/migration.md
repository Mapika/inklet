# Moving to Inklet

The package and Python import are now `inklet`. The figure API is the same:

```python
import inklet

fig = inklet.figure(width="89mm")
fig.add(inklet.box("Hello, Inklet"))
fig.save("hello.svg")
```

For an existing development checkout, replace the old editable installation:

```bash
uv pip uninstall dgm
uv pip install -e ".[dev]"
```

Update `import dgm` and `from dgm...` to use `inklet`, along with qualified
calls such as `inklet.figure(...)`. There is no `dgm` compatibility package.

| Previous name | Inklet name |
| --- | --- |
| `DGM_CACHE_DIR` | `INKLET_CACHE_DIR` |
| `DGM_BLENDER` | `INKLET_BLENDER` |
| `mouse.dgm.json` asset sidecar | `mouse.inklet.json` |
| Default cache directory `$XDG_CACHE_HOME/dgm/assets` | `$XDG_CACHE_HOME/inklet/assets` |

Rename existing sidecars to keep their anchors and attribution available.
Derived assets rebuild in the new cache directory; `INKLET_CACHE_DIR` can point
to an existing cache if you want to reuse it. When `XDG_CACHE_HOME` is unset,
the cache lives under `~/.cache`.

New SVG and PDF exports identify Inklet in their metadata. SVG background IDs
and generated font names also use the new prefix, so output bytes change even
when a figure's geometry is identical.

## V2 documents

Existing `inklet.figure()`, `panel()`, diagrams and SVG/PDF exports remain
supported. The live document API was introduced in 2.0 and extended in 2.5.

| Existing authoring | Live v2 equivalent |
|---|---|
| `p = inklet.panel(40, 30, ...)` | `p = inklet.plot_spec(40, 30, ...)` |
| `fig.add(p.build())` | `doc.add('panel', p)` |
| Recreate a panel after changing data | Keep data in `Dataset`; call `update()` |
| Add axes before outside keys/insets | Record instructions in any order; compilation resolves phases |
| Manually repeat colours and legend names | Use `Series` or `CategoryEncoding` |
| `fig.save('f.svg', 'f.pdf')` | `doc.save('f.svg', 'f.pdf')` |
| Inspect separate files after every edit | `inklet watch author.py --output out/review` |

V2 documents default to embedded, searchable text in SVG and PDF. Legacy
`Figure.save()` keeps its existing defaults. A compiled document is a snapshot;
a later edit requires `doc.compile()` again and does not mutate prior output.
Use `key=` to name plot instructions you intend to revise. Calling a drawing
method again adds another instruction; `replace(key, ...)` revises one.

For a new project, start with the [quickstart](quickstart.md) and
[authoring model](concepts.md). The [v2.5 guide](v2.5.md) covers nested grids,
measured compositions, publication defaults and revision review.

The new layout preserves typography. It raises `LayoutError` when cells cannot
fit the requested page. Fixed Diagram and Panel inputs retain their original
size. See [the v2 guide](v2.md) for live plot and component definitions.
