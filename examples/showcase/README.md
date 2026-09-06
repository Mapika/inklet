# Inklet showcase recipes

Eight figures cover mathematical plots, procedural 3D illustrations and an
architectural scene rendered with authored materials and a sketch style.

From an Inklet checkout:

```sh
python -m pip install -e '.[render,images]'
python tools/showcase_gallery.py --list
python tools/showcase_gallery.py --plots-only
python tools/showcase_gallery.py --download-assets --quality final --archive
```

Blender 4.2 LTS is required for 3D entries. The full collection downloads about
12 MB of pinned CC0 furniture files, then generates four editable `.blend`
scenes. Downloads are opt-in, cached and verified against SHA-256 hashes in
`assets.lock.json`. All other scene geometry is original procedural code.

Open `out/showcase/index.html`. Each entry includes SVG, PDF, PNG and an HTML
review. `catalog.json` records its data origin, asset credits, diagnostics and
rendered-image hash. `--archive` writes `out/inklet-showcase.zip`. Architectural
scene files pack their textures and can be opened on another machine.
`source/` contains copies of the recipes for reference;
run the builder from a full repository checkout to retain its expected paths.

Use `--quality draft` for quick composition checks, `preview` for review and
`final` for shareable renders. `--only architecture architecture-sketch` builds
a subset. A subset build replaces the index/catalogue with that selection;
previous export folders remain on disk.

The plots use explicit mathematical definitions and deterministic numerical
integration. The photonic device, lattice and helices are illustrations, not
experimental data or simulation results. The architecture scene is a concept,
not a construction drawing. The sketch is generated from 3D geometry.

The armchair is **Modern Arm Chair 01**, by **Vibrant Nordic**, distributed by
[Poly Haven](https://polyhaven.com/a/modern_arm_chair_01) under
[CC0](https://polyhaven.com/license). The chair mesh and textures are downloaded
to `out/showcase/assets/`; they are not included in Inklet's Python package.
Generated gallery images may be used to demonstrate Inklet; keep these credits
when redistributing the collection so its sources remain clear.
