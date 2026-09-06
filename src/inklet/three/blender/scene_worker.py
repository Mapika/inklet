"""Executed by Blender's Python, never imported by Inklet's interpreter."""
import json
import hashlib
import glob
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def run(request):
    scene = bpy.data.scenes.get(request['scene']) if request['scene'] else bpy.context.scene
    if scene is None:
        raise ValueError(f"Scene not found: {request['scene']!r}")
    bpy.context.window.scene = scene
    if request['camera']:
        scene.camera = scene.objects.get(request['camera'])
    camera = scene.camera
    if camera is None or camera.type != 'CAMERA':
        raise ValueError('Select an existing camera in the Blender scene')
    if camera.data.type not in ('PERSP', 'ORTHO'):
        raise ValueError('Scene anchors support perspective and orthographic cameras')
    if request['frame'] is not None:
        scene.frame_set(request['frame'])
    allowed = None
    if request['objects'] is not None or request['collections'] is not None:
        allowed = set(request['objects'] or ())
        for name in allowed:
            if name not in scene.objects:
                raise ValueError(f'Object not found: {name!r}')
        for name in request['collections'] or ():
            collection = bpy.data.collections.get(name)
            if collection is None:
                raise ValueError(f'Collection not found: {name!r}')
            allowed.update(obj.name for obj in collection.all_objects)
        for obj in scene.objects:
            if obj.type not in ('LIGHT', 'CAMERA', 'EMPTY') and obj.name not in allowed:
                obj.hide_render = True
    for name, properties in request['bindings'].items():
        obj = scene.objects.get(name)
        if obj is None:
            raise ValueError(f'Binding object not found: {name!r}')
        for key, value in properties.items():
            if key == 'color':
                if not hasattr(obj.data, 'materials'):
                    raise ValueError(f'{name!r} cannot have a material')
                # Material slots may be shared by several objects in an authored scene.
                obj.data = obj.data.copy()
                if not obj.data.materials:
                    obj.data.materials.append(bpy.data.materials.new(name+' Inklet'))
                for index, material in enumerate(obj.data.materials):
                    material = material.copy() if material else bpy.data.materials.new(name+' Inklet')
                    obj.data.materials[index] = material
                    material.diffuse_color = value
                    material.use_nodes = True
                    for node in material.node_tree.nodes:
                        if node.type == 'BSDF_PRINCIPLED':
                            for link in list(node.inputs['Base Color'].links):
                                material.node_tree.links.remove(link)
                            node.inputs['Base Color'].default_value = value
            else:
                setattr(obj, key, value)
    scene.render.engine = request['engine'] or scene.render.engine
    if scene.render.engine not in ('CYCLES', 'BLENDER_EEVEE_NEXT'):
        raise ValueError('Scene rendering supports CYCLES and BLENDER_EEVEE_NEXT')
    if scene.render.engine == 'CYCLES':
        scene.cycles.samples = request['samples']
        scene.cycles.seed = request['seed']
        scene.cycles.use_animated_seed = False
        scene.cycles.device = 'CPU'
    else:
        scene.eevee.taa_render_samples = request['samples']
    # The requested frame is the entire page, independent of authored crop borders.
    original_aspect = (scene.render.resolution_y*scene.render.pixel_aspect_y /
                       (scene.render.resolution_x*scene.render.pixel_aspect_x))
    width = request['width']
    height = request['height'] or width*original_aspect
    pixels = [max(1, round(width*request['dpi']/25.4)), max(1, round(height*request['dpi']/25.4))]
    if pixels[0]*pixels[1] > request['max_pixels']:
        raise ValueError('Scene exceeds max_pixels; reduce DPI or physical dimensions')
    scene.render.resolution_x, scene.render.resolution_y = pixels
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.use_multiview = False
    scene.render.film_transparent = request['transparent']
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.use_file_extension = True
    scene.render.use_stamp = False
    # Arbitrary compositor output nodes can overwrite authored files. Render the
    # scene image only; do not execute file-output nodes or the sequencer.
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = request['threads']
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_camera = camera.evaluated_get(depsgraph)
    anchors = {}
    for name, target in request['landmarks'].items():
        obj = None
        if isinstance(target, str):
            obj = scene.objects.get(target)
            if obj is None:
                raise ValueError(f'Landmark object not found: {target!r}')
            point = obj.evaluated_get(depsgraph).matrix_world.translation
        elif isinstance(target, dict):
            obj = scene.objects.get(target['object'])
            if obj is None:
                raise ValueError(f"Landmark object not found: {target['object']!r}")
            point = obj.evaluated_get(depsgraph).matrix_world @ Vector(target['point'])
        else:
            point = Vector(target)
        projected = world_to_camera_view(scene, evaluated_camera, point)
        in_frame = (camera.data.clip_start <= projected.z <= camera.data.clip_end and
                    0 <= projected.x <= 1 and 0 <= projected.y <= 1)
        origin = evaluated_camera.matrix_world.translation
        if camera.data.type == 'ORTHO':
            direction = evaluated_camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
            origin = point-direction*projected.z
        delta = point-origin
        # Visibility is a geometric surface test, not optical transmission.
        hidden = None
        if in_frame and delta.length > 1e-9:
            hit, location, _, _, hit_obj, _ = scene.ray_cast(depsgraph, origin, delta.normalized(), distance=delta.length+1e-5)
            hidden = bool(hit and (location-origin).length < delta.length-1e-4 and
                          (obj is None or hit_obj.original != obj.original))
        anchors[name] = dict(x_mm=projected.x*width, y_mm=(1-projected.y)*height,
                             depth=float(projected.z), in_frame=in_frame, occluded=hidden,
                             world=list(point))
    dependencies = sorted(set(bpy.utils.blend_paths(absolute=True, packed=False, local=False)))
    dependency_hashes = {}
    for path in dependencies:
        paths = glob.glob(path.replace('<UDIM>', '[0-9][0-9][0-9][0-9]')) if '<UDIM>' in path else [path]
        if not paths: raise ValueError(f'Missing scene asset: {path}')
        for filename in paths:
            with open(filename,'rb') as stream:
                dependency_hashes[str(Path(filename).resolve())] = hashlib.file_digest(stream,'sha256').hexdigest()
    result = dict(scene=scene.name, camera=camera.name, frame=scene.frame_current,
                  width_mm=width, height_mm=height, pixels=pixels,
                  engine=scene.render.engine, blender=bpy.app.version_string,
                  color_management=dict(view_transform=scene.view_settings.view_transform,
                      look=scene.view_settings.look, exposure=scene.view_settings.exposure,
                      gamma=scene.view_settings.gamma),
                  landmarks=anchors, dependencies=dependencies, dependency_hashes=dependency_hashes)
    stage = Path(request['output'])
    scene.render.filepath = str(stage/'image.png')
    bpy.ops.render.render(write_still=True, scene=scene.name)
    (stage/'scene.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text()))
