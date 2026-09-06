# Designed porosity

A procedural strut lattice between two compression plates. **Inklet 3.0 development.**

![Designed porosity](../../gallery/showcase-lattice.png)

## What this figure shows

The specimen is an original 3 × 3 × 3 body-centred strut lattice. Its appearance demonstrates geometry and lighting. No mechanical simulation or measured result is implied.

## Run the example

Install the rendering extras from a development checkout. This example also requires Blender with Cycles and Freestyle. See [installation](../installation.md) for a development checkout and [showcase setup](../showcase.md#build-and-download-the-collection) for independent PDF previews.

```sh
python -m pip install -e '.[render,images]'
python tools/showcase_gallery.py --only lattice --quality final
```

Open `out/showcase/lattice/figure.html` to review the result. The same folder contains `figure.svg`, `figure.pdf` and `figure.png`.

## Adapt it

Change the scene geometry or materials in the scene builder, then render again. Camera and material overrides are described in the [Blender scene guide](../blender-scenes.md).

[Figure source](../../examples/showcase/figures.py) · [Scene builders](../../examples/showcase/blender_scenes.py) · [Back to the gallery](../examples.md)
