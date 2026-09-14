"""Import the licensed NIH model without changing its geometry or proportions."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def main():
    source, output = map(Path, sys.argv[sys.argv.index('--')+1:])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    mat = bpy.data.materials.new('Anatomy / blue-grey')
    mat.use_nodes = True
    shader = mat.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = (.24,.45,.51,1)
    shader.inputs['Roughness'].default_value = .48
    for obj in objects:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for face in obj.data.polygons:
            face.use_smooth = True
    bounds = [obj.matrix_world@Vector(corner) for obj in objects for corner in obj.bound_box]
    lo, hi = [Vector([fn(p[k] for p in bounds) for k in range(3)]) for fn in (min,max)]
    centre = (lo+hi)/2
    extent = max(hi-lo)
    for name, direction, target, scale in [
        ('Overview', (0,-4,.3), centre, extent*1.3),
        ('Oblique', (2.5,-4,.8), centre, extent*1.3),
    ]:
        bpy.ops.object.camera_add(location=target+Vector(direction)*extent)
        camera = bpy.context.object
        camera.name = name
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.type = 'ORTHO'
        camera.data.ortho_scale = scale
    scene = bpy.context.scene
    scene.camera = bpy.data.objects['Overview']
    scene.render.resolution_x, scene.render.resolution_y = 1000,1200
    scene.world = bpy.data.worlds.new('World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (1,1,1,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .35
    for direction, power in [((1,-3,4),500), ((-3,-1,2),300), ((1,3,3),600)]:
        bpy.ops.object.light_add(type='AREA', location=centre+Vector(direction)*extent)
        light = bpy.context.object
        light.data.energy = power
        light.data.size = extent*3
        light.rotation_euler = (centre-light.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine = 'CYCLES'
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = 'AgX'
    # Surface anchors are ray intersections, not invented anatomical centroids.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    anchors = {}
    for name, camera_name, target in [
        ('Lung surface', 'Overview', (-.30, 0, -.12)),
        ('Upper airway', 'Overview', (0, 0, .38)),
        ('Vascular branches', 'Oblique', (.18, -.10, .10)),
        ('Source display base', 'Oblique', (0, -.10, -.72)),
    ]:
        origin = bpy.data.objects[camera_name].location
        ray = (Vector(target)-origin).normalized()
        hit, point, *_ = scene.ray_cast(depsgraph, origin, ray)
        if not hit:
            raise ValueError('No model surface at label target: '+name)
        anchors[name] = list(point)
    output.with_suffix('.anchors.json').write_text(json.dumps(anchors, indent=2))
    scene['source'] = 'NIH 3D 3DPX-023212 v1.01; kbrowne; CC BY 4.0'
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    output.with_suffix('.bounds.json').write_text(json.dumps({'min':list(lo),'max':list(hi)}))


if __name__ == '__main__':
    main()
