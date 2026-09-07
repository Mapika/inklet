"""Add a candidate camera and an explicit geometry revision to the original lab."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

source, output, revision = sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.open_mainfile(filepath=str(Path(source).resolve()))
bpy.ops.object.camera_add(location=(-1, -4, 8))
camera = bpy.context.object
camera.name = 'Services'
camera.rotation_euler = (Vector((0, 1.35, 2.2))-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 8.5
# The old landmark approximated the centre of a curved pipe and sat behind its
# surface. Intersect that object's evaluated mesh from the services camera so
# every candidate uses one fixed, actual surface point on the named manifold.
pipe = bpy.data.objects['Exhaust manifold']
evaluated = pipe.evaluated_get(bpy.context.evaluated_depsgraph_get())
mesh = evaluated.to_mesh()
tree = BVHTree.FromPolygons([pipe.matrix_world @ v.co for v in mesh.vertices],
                           [tuple(p.vertices) for p in mesh.polygons])
target = bpy.data.objects['Target Exhaust manifold']
direction = (target.location-camera.location).normalized()
hit, _, _, _ = tree.ray_cast(camera.location, direction)
if hit is None:
    raise ValueError('The manifold landmark ray missed its geometry')
target.location = hit
evaluated.to_mesh_clear()
if revision == 'moved-gas':
    for obj in bpy.context.scene.objects:
        if obj.name.startswith(('Gas bottle', 'Gas valve', 'Pressure gauge', 'Target Gas supply')):
            obj.location.y -= .9
elif revision != 'original':
    raise ValueError('Unknown geometry revision')
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(Path(output).resolve()), compress=False)
