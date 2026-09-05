# Inklet module contract

The core represents geometry, styles, primitives and immutable diagram trees.
Typesetting measures text; layout places nodes; routing connects them;
diagnostics inspect the resolved figure; rendering exports it.

Core changes affect every layer. Preserve the invariants below and add focused
regression coverage for changes to measurement, placement or traversal.

## Non-negotiables

- **Millimetres everywhere.** `core.units.mm("89mm") -> 89.0`, `pt(7) -> 2.47`.
  Bare numbers are already mm. Pixels exist only inside a raster backend.
- **y grows downward** (SVG convention). North is `-y`.
- **Primitives are centred on their local origin.**
- **Deterministic output.** No `uuid4`, no dict-order dependence, no
  `time`/`random`. The same script must emit byte-identical SVG twice.
- **Core never measures text.** `TextPrim` arrives pre-shaped.
- Python 3.11 or later, `from __future__ import annotations`, dataclasses, type hints.
  Stdlib + the deps already in `pyproject.toml` only.

## Core API you build against

```python
Vec2(x, y)                  # + - * dot cross length normalized perp angle
Affine(a,b,c,d,e,f)         # .translation .rotation .scaling  A @ B = B then A
                            # .apply(pt) .apply_vector(v) .inverse() .is_identity
Rect(x0,y0,x1,y1)           # .width .height .center .corners .union .pad .overlap
Envelope                    # .extent(unit_dir) -> float|None   support function
                            # .union .transform .pad .bbox()
Trace                       # .exit(origin, dir) .boundary_point(origin, dir)
Style(...)                  # all fields Optional, None = inherit; .over(base) .with_()
Prim: RectPrim(w,h,radius) EllipsePrim(rx,ry)
      PathPrim(subpaths,filled,fill_rule)   # fill_rule: nonzero | evenodd
      TextPrim(lines,font_family,font_size,ascent,descent,align,font_path,
               ...,features)   # features = sorted (tag, value) pairs it was
                               # shaped with; core.text_features() canonicalises
      ImagePrim(source,width,height,pixel_size,outline,data,smooth)
                         # data = encoded PNG/JPEG bytes; then source is a label
                         # smooth: None = backend's call, False = nearest-neighbour
      PhantomPrim(box)   # occupies space, draws nothing, empty trace
Envelope.expand(t,r,b,l)   # padding: a disc sweep when uniform, box sum when not
Diagram(envelope_override=...)  # claim space the contents do not; trace untouched
Diagram(prim=, children=(), transform=, style=, kind=, name=, notes={})
  .local_envelope .envelope   # local = before self.transform; plain = after
  .local_trace .trace .bbox .local_bbox .width .height .extent(dir)
  .anchor(name, (u,v)|Vec2)   # (u,v) are fractions of local bbox, (0,0)=top-left
  .anchor_point(name)         # compass: n s e w ne nw se sw center. LOCAL:
                              # pre-transform. Placement.point re-reads the
                              # compass off the placed box (M10)
  .registered_point(name)     # a registered anchor, looking through the
                              # wrappers translated/rotated/scaled leave
                              # behind, or None (M16)
  .note(key, value) -> self   # per-node annotation core does not read;
  .notes                      # survives replace/apply_theme/build (M17)
  .carry_notes(source)        # inherit a single child's notes, moved into
                              # this node's frame (M19)
note_through(affine, value)   # how one note value moves: a Rect is re-cornered,
                              # everything else is carried verbatim (M19)
  .at(name) -> AnchorRef
  .placed(affine) .translated .rotated .scaled .centered .styled .named .copy
  .walk() .find(name)
resolve(root) -> {id: Placement}   # Placement: .world .style .envelope .trace
                                   #            .bbox .point(anchor) .depth
flatten(root) -> [RenderItem]      # RenderItem: .prim .world .style .id .name
world_point(ref_or_diagram, placements) -> Vec2
```

Combinators **wrap, never rewrite**: `d.translated(3)` returns a new parent
whose child is the very same `d` object, so a caller's handle stays valid after
being stacked. Never place one Diagram object twice — `resolve()` raises.

## Testing

`.venv/bin/python -m pytest tests/ -q`. Place regression tests alongside the relevant feature tests. Test behaviour
and numerical results.
