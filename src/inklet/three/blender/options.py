"""Which lines Line Art should find, and how much to tidy them afterwards.

There is deliberately no camera here. `inklet.three.camera.Camera` is the one
camera vocabulary in this package -- named presets, azimuth and elevation,
`look_at` -- and a second one that only Blender understood would be a trap for
anyone drawing the same mesh with both backends. This module names its fields
after `inklet.three.backend.Look` wherever the two mean the same thing, so wiring
one to the other is a rename and not a translation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .discover import BlenderError

__all__ = ["LineArtOptions", "FITS", "UP_AXES", "DEFAULT_CREASE_DEGREES"]

FITS = ("content", "frame")
UP_AXES = ("y", "z")

#: The same 30 degrees `inklet.three.edges` defaults to, and for the same reason:
#: it keeps a subdivided sphere's facets quiet while still inking the corner of
#: a box. Measured between adjacent face normals, so 0 draws every edge and
#: 180 draws none. See `LineArtOptions.crease` for why a scanned surface wants
#: a very different number from a machined part.
DEFAULT_CREASE_DEGREES = 30.0


@dataclass(frozen=True)
class LineArtOptions:
    """What to draw. The defaults draw an object the way an illustrator would:
    its outline, the folds sharp enough to read as folds, and nothing else.

    Intersection lines are off because they only exist in an assembly, and a
    single mesh pays for the test without getting anything back.

    `chain_gap` is what makes the result look drawn rather than shattered. Line
    Art produces one stroke per visible edge fragment; without chaining, a
    subdivided sphere comes back as hundreds of three-point stubs and every
    round join in the rendered stroke shows. The number is a fraction of the
    frame: fragments whose ends land closer than that become one stroke.

    Modelled and scanned surfaces want opposite settings, and the difference is
    `crease`. On a machined part the creases *are* the drawing -- the fillets
    and chamfers a contour never sees -- and the default 30 degrees finds them.
    On a scanned organic surface there is no such thing as a designed fold:
    every triangle meets its neighbour at a few degrees, so a low threshold
    inks the triangulation itself. Baking `stress/meshes/brain-lh.obj` (18000
    faces) at a run of thresholds shows exactly where the crossover is:

        crease   0    10    20    30    45    60    94   180
        strokes  1513 1408  1235  1036  768   523   349  301

    Everything below 45 is visibly a wireframe of the mesh, not a drawing of
    the brain. Above 60 the count flattens towards the 301 strokes that
    `crease=180` -- creases off entirely -- produces on its own, because on a
    convoluted surface almost all the readable line work is *contour*: every
    sulcus turns away from the eye and gets an occluding contour for free.

    So for a scan, prefer `shade_smooth=True` over hunting for a threshold. It
    smooths the normals and stops Line Art creasing across them, which is
    crease-independent by construction and gives the same clean 301 strokes at
    any setting. It is off by default because it is wrong for a CAD part, where
    it would erase the very edges the drawing is about.

    Two limits worth knowing before they cost you an afternoon:

    * Decimation has a floor. Around 40000 faces a cortical surface still holds
      its gyri; at 14000 the same view degrades to noise, because the folds are
      no longer resolved and what survives is triangulation. Simplify for speed
      by all means, but look at the result rather than trusting a face budget.
    * Multi-part meshes are not supported as a single body. Line Art draws a
      contour for every object it can see, so a labelled anatomical atlas whose
      42 regions interpenetrate comes back as a scribble of 42 overlapping
      outlines. Bake one closed manifold at a time.
    """

    contour: bool = True                       # the occluding outline
    crease: float = DEFAULT_CREASE_DEGREES     # degrees between face normals
    hidden: bool = True                        # remove hidden lines; False is an x-ray
    cull: bool | None = None                   # None asks Line Art; True skips back faces
    intersection: bool = False                 # where two solids interpenetrate
    material: bool = False                     # boundaries between material slots
    edge_marks: bool = False                   # edges the modeller marked by hand
    loose: bool = False                        # wire edges belonging to no face
    silhouette: bool = True                    # also bake the outer outline on its own layer
    thickness: int = 1                         # Line Art's own units; the exported width is discarded
    chain_gap: float = 0.01                    # fraction of the frame; 0 disables chaining
    smooth: float = 0.0                        # stroke smoothing tolerance
    sample: float = 0.0                        # resample distance on export, 0 keeps every point
    subdivide: int = 0                         # Catmull-Clark levels applied before baking
    shade_smooth: bool = False                 # smooth normals, and stop creasing across them (see above)
    overscan: float = 0.1                      # fraction of frame computed outside it, so edges chain

    def __post_init__(self) -> None:
        if not 0.0 <= self.crease <= 180.0:
            raise BlenderError(
                f"crease is the angle in degrees between adjacent face normals "
                f"and must be in [0, 180], not {self.crease}"
            )
        if not any((self.contour, self.crease < 180.0, self.intersection,
                    self.material, self.edge_marks, self.loose)):
            raise BlenderError(
                "every line type is switched off, so there is nothing to draw; "
                "leave contour=True or lower the crease angle"
            )
        if not 0 <= self.subdivide <= 4:
            raise BlenderError(
                f"subdivide must be 0-4 levels, not {self.subdivide}; each level "
                "quadruples the face count and level 5 of a 50k mesh is 51 "
                "million faces"
            )
        if self.thickness < 1:
            raise BlenderError(f"thickness must be at least 1, not {self.thickness}")
        for name in ("chain_gap", "smooth", "sample", "overscan"):
            if getattr(self, name) < 0:
                raise BlenderError(f"{name} cannot be negative")

    def key(self) -> dict[str, Any]:
        """Every field that changes the bake. The cache hashes this, so a field
        added above and forgotten here would serve a stale drawing."""
        return {
            "contour": self.contour, "crease": self.crease,
            "hidden": self.hidden, "cull": self.cull,
            "intersection": self.intersection, "material": self.material,
            "edge_marks": self.edge_marks, "loose": self.loose,
            "silhouette": self.silhouette, "thickness": self.thickness,
            "chain_gap": self.chain_gap, "smooth": self.smooth,
            "sample": self.sample, "subdivide": self.subdivide,
            "shade_smooth": self.shade_smooth, "overscan": self.overscan,
        }
