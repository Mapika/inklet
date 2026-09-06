# An architectural interior

Authored materials, textured furniture and an orthographic camera. **Inklet 3.0 development.**

![An architectural interior](../../gallery/showcase-architecture.png)

## What this figure shows

The room geometry and lighting are authored in Blender. The chair is Modern Arm Chair 01 by Vibrant Nordic / Poly Haven (CC0). The scene packs its textures. This is a conceptual interior, not a measured design or construction drawing.

## Run the example

Install the rendering extras from a development checkout. This example also requires Blender with Cycles and Freestyle. The first build downloads about 12 MB of CC0 furniture and textures; every file is checked against the asset lock. See [installation](../installation.md) for a development checkout and [showcase setup](../showcase.md#build-and-download-the-collection) for independent PDF previews.

```sh
python -m pip install -e '.[render,images]'
python tools/showcase_gallery.py --only architecture --quality final --download-assets
```

Open `out/showcase/architecture/figure.html` to review the result. The same folder contains `figure.svg`, `figure.pdf` and `figure.png`.

## Adapt it

Change the scene geometry or materials in the scene builder, then render again. Camera and material overrides are described in the [Blender scene guide](../blender-scenes.md).

[Figure source](../../examples/showcase/figures.py) · [Scene builders](../../examples/showcase/blender_scenes.py) · [Back to the gallery](../examples.md)

[Chair source and licence](../showcase.md#reuse-and-interpretation) · [GPU rendering and annotations](../render-jobs.md)
