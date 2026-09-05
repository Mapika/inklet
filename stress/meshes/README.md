# Test meshes

These meshes are recentered and normalized into a two-unit cube. Their original
units are not anatomical measurements in these files.

| File | Faces | Geometry | Source and terms |
| --- | ---: | --- | --- |
| `spot.obj` | 5,856 | Open eye and mouth boundaries | Keenan Crane, [model repository](https://www.cs.cmu.edu/~kmcrane/Projects/ModelRepository/), CC0 1.0 |
| `brain-lh.obj` | 18,000 | Closed left cerebral cortical surface | Neuroscape / Gazzaley Lab, UCSF, [NIH 3D entry](https://3d.nih.gov/entries/3DPX-000757), CC0 1.0 |

See [third-party notices](../../THIRD_PARTY_NOTICES.md) for attribution,
modifications and source terms. Tests that need small exact geometry generate
it locally; the scanned cortical surface exercises dense overlap and sorting.
