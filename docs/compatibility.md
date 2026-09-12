# Compatibility

Inklet **3.1** supports the environments and rendering paths below.
The matrix distinguishes installed-package checks from full integration tests.

## Test coverage

| Area | Automated coverage | Limits |
| --- | --- | --- |
| Core and `render` wheels | Ubuntu 24.04 / Python 3.11, 3.12, 3.13; Windows 2022 and macOS 14 / Python 3.12 | Installed-package smoke checks on Windows/macOS; full suite on Linux |
| Complete figures | Linux, pinned Python dependencies, DejaVu/Noto fonts, resvg, Chromium and Poppler | Pixel baselines depend on those fonts and renderers |
| Complete Blender scenes | Linux CPU, Blender 4.2.23 and 4.5.13 LTS | Other Blender builds/platforms are not covered by scene CI |
| Cycles GPU | Local Blender 4.5.13 CUDA check on an RTX 5090 Laptop GPU | GPU CI is unavailable; OptiX, HIP, oneAPI and Metal are not verified on hardware |
| Vector line-art baking | Blender 4.2 LTS, locally tested on Linux | Newer Grease Pencil APIs are incompatible with this legacy backend |
| Native vector 3D | Core package and full figure tests | No Blender or GPU required |

The [release workflow](../.github/workflows/checks.yml) is the current source of
automated coverage. Python 3.11 is the minimum; later versions outside the
matrix are not yet verified. A successful smoke test checks installation and
representative exports, not every OS-specific behavior or font substitution.

Blender CI downloads fixed builds from the official release archive and verifies
pinned SHA-256 hashes. It requires the requested version before running tests,
so a failed installation cannot turn the scene tests into a green skipped run.
Each version also creates and renders all three templates from an installed
wheel in an isolated environment.

## Optional dependencies

| Capability | Requirement |
| --- | --- |
| Plots, diagrams, SVG/PDF, native 3D | Core package and a usable installed font |
| PNG, explicit masks and rasterization | `render` extra |
| Raster images in PDF | Pillow, included in `render` and `images` |
| Pass access with `value()` | Core package; no NumPy |
| Pass arrays and `.npy` export | NumPy, included in `images` and `three` |
| Experimental microscopy, TIFF and label tables | `volume` extra; APIs and schemas may change |
| Additional mesh formats/repair | `three` extra |
| `.blend` authoring/rendering | Separate Blender installation; `render` extra for figure exports |
| Independent PDF preview | Poppler; optional with `compare_pdf=False` |
| Chromium preview | Separate Chrome/Chromium; explicitly selected |

Importing Inklet and reading `scene_templates()` does not discover or start
Blender. Scene creation and rendering run Blender in a separate process.

## Known boundaries

### Development-preview table adapters

The [pandas and Polars adapters](table-inputs.md) are included in the experimental
[4.0.0.dev6 preview](development-preview.md), not in stable 3.1.0. Their `pandas` and `polars` extras are separate
from core dependencies. The adapter CI jobs use Linux/Python 3.12 with pandas
2.2.0 / Polars 1.0.0 and the versions pinned in `requirements-tables.txt`.
Both paths check scalar/identity contracts and saved-state SVG reconstruction.
The core wheel checks that neither integration is required or imported.

### Rendering

The legacy vector line-art backend uses Blender's pre-4.3 Grease Pencil API.
Blender documents that incompatible transition in its
[migration guide](https://developer.blender.org/docs/release_notes/4.3/grease_pencil_migration/).
Inklet reports the required 4.2 version before starting a new line-art bake.
This is separate from complete `.blend` scene rendering and the raster sketch
style, both tested with 4.5.

Cycles GPU selection depends on the installed Blender build and drivers.
`AUTO` falls back when no usable GPU is discovered; it does not conceal a render
failure by retrying on CPU. EEVEE needs a working graphics context and has no
headless CI guarantee. See [device behavior](render-jobs.md).

Depth-tested overlays sample the saved depth image. Glass, thin geometry,
silhouettes and object-index masks have documented
[precision limits](scene-paths.md#precision-and-limits). Scene masks are not
Cryptomatte. User compositors, embedded Python execution, animation/video export
and arbitrary simulation bindings are outside the 3.1 feature set.

Template creation preserves existing files on failure. Its default atomic
no-overwrite commit requires filesystem hard-link support; explicit
`overwrite=True` uses atomic replacement. See [template creation](scene-templates.md).

## Release acceptance

Before a stable tag:

1. Require green figure, wheel and Blender jobs on the exact release commit.
2. Build the wheel and source archive, check metadata with Twine, and run isolated
   wheel checks against those files. Build the wheel from the source archive too.
3. Review the rendered examples and verify `latest` docs point to the release
   commit. Follow the [3.1 migration guidance](migration.md#from-30-to-31).
4. Freeze the release files with `SHA256SUMS`, then attach those exact files to
   the release. The [publishing workflow](release-checks.md#publishing-to-pypi)
   is a separate manual step.

Package publication is separate from validation. These checks do not upload
anything to PyPI.
