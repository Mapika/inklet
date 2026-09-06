# Deterministic chaos

A Lorenz trajectory, drawn as continuous vector strokes. **Inklet 3.0 development.**

![Deterministic chaos](../../gallery/showcase-attractor.png)

## What this figure shows

The trajectory is integrated with fourth-order Runge–Kutta, using a fixed initial state and time step. Consecutive segments share endpoints. Colour indicates elapsed integration time.

## Run the example

Install the rendering extras from a development checkout. This example does not require Blender or downloaded assets. See [installation](../installation.md) for a development checkout and [showcase setup](../showcase.md#build-and-download-the-collection) for independent PDF previews.

```sh
python -m pip install -e '.[render,images]'
python tools/showcase_gallery.py --only attractor --quality final
```

Open `out/showcase/attractor/figure.html` to review the result. The same folder contains `figure.svg`, `figure.pdf` and `figure.png`.

## Adapt it

Change the data definition, ranges or colours in the `attractor()` builder. This is the function used by the gallery recipe:

<!-- recipe:attractor -->

[Figure source](../../examples/showcase/figures.py) · [Scene builders](../../examples/showcase/blender_scenes.py) · [Back to the gallery](../examples.md)
