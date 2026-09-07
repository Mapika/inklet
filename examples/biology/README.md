# Source data for the real-biology example

`organelle.lock.json` pins 200 N5 metadata/chunk locations at pyramid level s4
of COSEM's jrc_hela-3 dataset. Eight locations were absent (zero-filled N5
background). The remaining 192 objects total 56,570,199 bytes. The fetcher
verifies each object's SHA-256 and size before local reading.

Source: https://registry.opendata.aws/janelia-cosem/
License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/
Attribution: COSEM Project Team / HHMI Janelia Research Campus; Heinrich et al.,
*Whole-cell organelle segmentation in volume electron microscopy*, Nature 599,
141–146 (2021), https://doi.org/10.1038/s41586-021-03977-3.

See `../../THIRD_PARTY_NOTICES.md`. The data and derived gallery image retain
CC BY 4.0. Python implementation code is MIT.

Install `inklet[volume,render]` and this directory's `requirements.txt`, then run
`python examples/real_biology.py --blender /path/to/blender` from the checkout.
Raw files remain in `out/real-biology/source.n5/`. Source N5 labels are automatic
segmentation estimates, not new annotations or ground truth produced by Inklet.
The example does not download the much larger full-resolution dataset.
