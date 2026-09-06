# Installation

Inklet requires Python 3.11 or later and an installed TrueType/OpenType font.
The core Python dependencies are HarfBuzz bindings and fontTools.

## From PyPI

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install inklet
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead.
If your system calls Python `python3`, use that command to create the environment.
The remaining commands assume an activated environment.

With `uv`, use `uv venv --python 3.12` followed by `uv pip install inklet`.
Activate the environment or prefix commands with `.venv/bin/` on Linux/macOS.

## Optional features

| Install from PyPI | Adds |
|---|---|
| `python -m pip install 'inklet[images]'` | Pillow and NumPy for images, raster layers and PNG previews |
| `python -m pip install 'inklet[three]'` | Trimesh and NumPy for additional mesh formats and optional repair |

Extras can be combined: `python -m pip install 'inklet[images,three]'`.
The built-in 3D renderer works without the `three` extra or Blender. Optional
cutout/tracing tools such as `rembg` and `potrace` are not included in `images`.

## From a checkout

```sh
git clone https://github.com/Mapika/inklet.git
cd inklet
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead.
The remaining commands use the activated environment. If your system calls
Python `python3`, use that command to create the environment.

With `uv`, the equivalent environment setup is:

```sh
uv venv --python 3.12
uv pip install -e .
```

Activate that environment or prefix commands with `.venv/bin/` on Linux/macOS.
Check the installed package with
`python -c "import inklet; print(inklet.__version__)"`.

### Checkout extras

| Install from the checkout | Adds |
|---|---|
| `python -m pip install -e '.[render]'` | Browser-free PNG, masks and raster layers (v3) |
| `python -m pip install -e '.[images]'` | Pillow and NumPy for images, raster layers and PNG previews |
| `python -m pip install -e '.[three]'` | Trimesh and NumPy for additional mesh formats and optional repair |
| `python -m pip install -e '.[dev]'` | Pytest for development |
| `python -m pip install -e '.[docs]'` | MkDocs for the searchable documentation site |

Extras can be combined: `python -m pip install -e '.[dev,images,three,docs]'`.

## Fonts

Inklet shapes text using installed fonts. Fontconfig is preferred for finding
families and fallback glyphs; a filesystem scan is used when it is unavailable.
For reproducible output, install the same fonts on development and build machines.

On Debian/Ubuntu, a useful baseline is:

```sh
sudo apt-get install fontconfig fonts-dejavu-core fonts-dejavu-extra fonts-noto-core
```

Use an explicit family or font file when the default substitution is unsuitable.
Low-level text uses `size=i.pt(8)` for 8-point type. See
[units and themes](concepts.md#physical-units).

## Visual review

V3 development uses resvg for PNG output and review previews. Install from a
checkout with `python -m pip install -e '.[render]'`. SVG and PDF saving need no
browser; figures containing raster images also need Pillow (included in `render`).

Poppler's `pdftoppm` supplies the independent PDF preview. Install `poppler-utils`
on Debian/Ubuntu or `brew install poppler` on macOS. `--no-pdf-preview` omits that
comparison while retaining the PDF file and HTML review.

Chrome/Chromium is only needed for the explicit `--png-backend chromium` preview
path or the independent SVG regression tests. See [Blender scenes](blender-scenes.md)
for optional Blender setup. Released 2.6 uses the earlier Chromium preview path;
its instructions are in the [stable guide](https://inklet.readthedocs.io/en/stable/installation/).

```sh
python -m inklet doctor
```

`doctor` prints detected tools and Python packages as JSON. It is an environment
report, not a figure validation command; absent optional tools do not make it
exit with an error.

Without preview tools, use [the quickstart](quickstart.md) and save vectors, or:

```sh
inklet build examples/v25_document.py --output out/v25 --vectors-only
```

`--no-pdf-preview` plus the `render` extra creates a review without Chrome or Poppler.

## Build the documentation

```sh
python -m pip install -e '.[docs]'
python -m mkdocs serve
```

Open `http://127.0.0.1:8000/`. For a static build, run
`python -m mkdocs build --strict`; output goes to `out/docs-site/`.
The site is built locally or as a CI artifact; these commands do not publish it.
