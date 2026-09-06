# Travelling wave packets

Eighteen offset signals with a consistent drawing order. **Inklet 3.0 development.**

![Travelling wave packets](../../gallery/showcase-wave-packets.png)

## What this figure shows

Each trace is a Gaussian-windowed oscillation at a different parameter value. Rear traces are drawn first, so foreground fills cover the correct curves. Vertical offsets separate the signals; they are not amplitude measurements.

## Run the example

Install the rendering extras from a development checkout. This example does not require Blender or downloaded assets. See [installation](../installation.md) for a development checkout and [showcase setup](../showcase.md#build-and-download-the-collection) for independent PDF previews.

```sh
python -m pip install -e '.[render,images]'
python tools/showcase_gallery.py --only wave-packets --quality final
```

Open `out/showcase/wave-packets/figure.html` to review the result. The same folder contains `figure.svg`, `figure.pdf` and `figure.png`.

## Adapt it

Change the data definition, ranges or colours in the `wave_packets()` builder. This is the function used by the gallery recipe:

<!-- recipe:wave_packets -->

[Figure source](../../examples/showcase/figures.py) · [Scene builders](../../examples/showcase/blender_scenes.py) · [Back to the gallery](../examples.md)
