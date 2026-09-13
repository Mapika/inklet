"""Original schematic synapse geometry; no measured biological dimensions."""
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Vector


def material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Roughness'].default_value = .38
    return mat


def sphere(name, position, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def main():
    output = Path(sys.argv[sys.argv.index('--') + 1])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    membrane = material('Terminal membrane', (.34, .53, .59))
    vesicle = material('Vesicle membrane', (.48, .30, .62))
    post = material('Postsynaptic membrane', (.80, .60, .48))
    receptor = material('Receptors', (.025, .35, .40))
    signal = material('Release particles', (.95, .55, .10))
    # Back half of an ellipsoidal shell; the front is removed for visibility.
    vertices, faces = [], []
    rows, columns = 32, 48
    for j in range(rows + 1):
        theta = .07 + (math.pi - .14) * j / rows
        for k in range(columns + 1):
            phi = math.pi * k / columns
            vertices.append((2.65 * math.sin(theta) * math.cos(phi),
                             1.6 * math.sin(theta) * math.sin(phi),
                             2.15 + 1.45 * math.cos(theta)))
    for j in range(rows):
        for k in range(columns):
            a = j * (columns + 1) + k
            faces.append((a, a+1, a+columns+2, a+columns+1))
    mesh = bpy.data.meshes.new('Cutaway shell')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new('Presynaptic cutaway', mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(membrane)
    shell = obj.modifiers.new('Membrane thickness', 'SOLIDIFY')
    shell.thickness = .09
    for face in mesh.polygons:
        face.use_smooth = True
    sphere('Active zone', (0, .1, .72), (2.2, 1.35, .12), membrane)
    sphere('Postsynaptic surface', (0, 0, -.22), (3.1, 2.0, .22), post)
    rng = random.Random(23)
    positions = [(-1.5, -.1, 1.8), (-.6, -.25, 2.3), (.6, -.2, 1.75),
                 (1.55, .05, 2.2), (-.4, .45, 1.2), (.7, .6, 2.8),
                 (-1.4, .55, 2.65), (1.55, .6, 1.25)]
    for n, position in enumerate(positions):
        sphere(f'Vesicle {n+1}', position, (.29, .29, .29), vesicle)
        for k in range(7):
            offset = Vector((rng.uniform(-.18, .18), rng.uniform(-.18, .18), rng.uniform(-.18, .18)))
            sphere(f'Cargo {n}-{k}', Vector(position)+offset, (.04,)*3, signal)
    for n, (x, y) in enumerate([(-1.5,-.6), (-.5,-.7), (.5,-.65), (1.5,-.4), (-.9,.4), (.9,.5)]):
        for side in (-1, 1):
            sphere(f'Receptor {n}-{side}', (x+side*.08, y, .10), (.065, .09, .25), receptor)
    for n in range(24):
        sphere(f'Released particle {n}', (rng.uniform(-.8,.8), rng.uniform(-.9,.15), rng.uniform(.28,.61)), (.045,)*3, signal)
    scene = bpy.context.scene
    bpy.ops.object.camera_add(location=(6,-10,6))
    camera = bpy.context.object
    camera.name = 'Overview'
    camera.rotation_euler = (Vector((0,0,1.4))-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 8.6
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = 1400, 1050
    scene.world = bpy.data.worlds.new('World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (1,1,1,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .35
    for position, power, size in [((1,-4,8),900,6), ((-5,-1,4),600,5), ((2,5,6),1000,4)]:
        bpy.ops.object.light_add(type='AREA', location=position)
        lamp = bpy.context.object
        lamp.data.energy, lamp.data.size = power, size
        lamp.rotation_euler = (Vector((0,0,1.4))-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = 'AgX'
    scene['description'] = 'Original illustrative synapse; arbitrary scene units, not measured anatomy.'
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


if __name__ == '__main__':
    main()
