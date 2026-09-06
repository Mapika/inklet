# Interference

Two radial waves, one shared colour scale. **Inklet 3.0 development.**

![Interference](../../gallery/showcase-interference.png)

## What this figure shows

The colour field is the sum of two analytic radial waves. Both sources use the same spatial grid and colour scale. The matrix is rasterised; axes and the colour bar remain vector elements.

## Run the example

Install the rendering extras from a development checkout. This example does not require Blender or downloaded assets. See [installation](../installation.md) for a development checkout and [showcase setup](../showcase.md#build-and-download-the-collection) for independent PDF previews.

```sh
python -m pip install -e '.[render,images]'
python tools/showcase_gallery.py --only interference --quality final
```

Open `out/showcase/interference/figure.html` to review the result. The same folder contains `figure.svg`, `figure.pdf` and `figure.png`.

## Adapt it

Change the data definition, ranges or colours in the `interference()` builder. This is the function used by the gallery recipe:

<!-- recipe:interference -->

[Figure source](../../examples/showcase/figures.py) · [Scene builders](../../examples/showcase/blender_scenes.py) · [Back to the gallery](../examples.md)
