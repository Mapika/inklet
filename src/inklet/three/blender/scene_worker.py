"""Executed by Blender's Python, never imported by Inklet's interpreter."""
import json
import hashlib
import glob
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def event(phase,message):
    print('INKLET_EVENT '+json.dumps(dict(phase=phase,message=message)),flush=True)


def select_device(scene,execution):
    backend=execution['backend']
    if backend=='CPU':
        scene.cycles.device='CPU'
        return
    preferences=bpy.context.preferences.addons['cycles'].preferences
    preferences.compute_device_type=backend
    found=preferences.get_devices_for_type(backend)
    selected={d['id'] for d in execution['devices']}
    available={d.id for d in found if d.type==backend}
    if not selected or not selected <= available:
        raise ValueError('Selected GPU devices are no longer available; refresh render_devices()')
    for item in preferences.devices:
        item.use=item.type==backend and item.id in selected
    if not preferences.has_active_device():
        raise ValueError('Blender could not activate the selected GPU devices')
    scene.cycles.device='GPU'


def prepare_passes(scene, layer, names, stage):
    """Use a fresh compositor; authored output nodes must never execute."""
    if not names:
        return {}
    if scene.render.engine != 'CYCLES':
        raise ValueError('Data passes currently require CYCLES')
    layer.use_pass_z = 'depth' in names
    layer.use_pass_normal = 'normal' in names
    layer.use_pass_object_index = 'object_id' in names
    object_ids = {}
    if 'object_id' in names:
        objects = sorted(scene.objects, key=lambda obj: obj.name)
        if len(objects) > 32767:
            raise ValueError('Object ID passes support at most 32767 scene objects')
        for index, obj in enumerate(objects, 1):
            obj.pass_index = index
            object_ids[obj.name] = index
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    source = tree.nodes.new('CompositorNodeRLayers')
    source.layer = layer.name
    composite = tree.nodes.new('CompositorNodeComposite')
    tree.links.new(source.outputs['Image'], composite.inputs['Image'])
    for name in names:
        output = tree.nodes.new('CompositorNodeOutputFile')
        output.base_path = str(stage)
        output.file_slots[0].path = name + '-'
        output.format.file_format = 'OPEN_EXR'
        output.format.color_depth = '32'
        output.format.color_mode = 'RGBA'
        socket = {'depth': 'Depth', 'normal': 'Normal', 'object_id': 'IndexOB'}[name]
        tree.links.new(source.outputs[socket], output.inputs[0])
    scene.render.use_compositing = True
    return object_ids


def collect_passes(names, stage, pixels):
    # NumPy ships inside Blender. The host can read individual values with only
    # the standard library; no EXR reader is required in an Inklet installation.
    import numpy as np
    result = {}
    for name in names:
        files = list(stage.glob(name + '-*.exr'))
        if len(files) != 1:
            raise ValueError(f'Expected one rendered {name} pass')
        image = bpy.data.images.load(str(files[0]), check_existing=False)
        image.colorspace_settings.name = 'Non-Color'
        values = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(values)
        channels = 3 if name == 'normal' else 1
        # Blender images start at bottom-left; Inklet arrays start at top-left.
        values = values.reshape(pixels[1], pixels[0], 4)[::-1, :, :channels]
        data = np.ascontiguousarray(values, dtype='<f4').tobytes()
        filename = name + '.f32'
        (stage / filename).write_bytes(data)
        result[name] = dict(file=filename, sha256=hashlib.sha256(data).hexdigest(),
                            channels=channels, dtype='<f4', origin='top-left')
        result[name].update({'depth': dict(units='Blender scene units', background=1e10),
                             'normal': dict(space='world', background=[0, 0, 0]),
                             'object_id': dict(background=0, antialiased=False)}[name])
        bpy.data.images.remove(image)
        files[0].unlink()
    return result


def sketch_style(scene, layer, dpi):
    if scene.render.engine != 'CYCLES' or not bpy.app.build_options.freestyle:
        raise ValueError('Sketch style requires Cycles and a Blender build with Freestyle')
    material = bpy.data.materials.new('Inklet sketch paper')
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (.82, .79, .72, 1)
    shader.inputs['Roughness'].default_value = 1
    layer.material_override = material
    scene.render.use_freestyle = True
    layer.use_freestyle = True
    scene.render.line_thickness_mode = 'ABSOLUTE'
    scene.render.line_thickness = 1
    settings = layer.freestyle_settings
    settings.mode = 'EDITOR'
    for item in list(settings.linesets):
        settings.linesets.remove(item)
    lines = settings.linesets.new('Inklet sketch contours')
    lines.select_silhouette = True
    lines.select_border = True
    lines.select_crease = True
    line = lines.linestyle
    line.color = (.045, .035, .025)
    line.thickness = .21 * dpi / 25.4
    noise = line.geometry_modifiers.new('Small pencil irregularity', 'SPATIAL_NOISE')
    noise.amplitude = .10 * dpi / 25.4
    noise.scale = 3 * dpi / 25.4
    noise.octaves = 2
    noise.smooth = True
    noise.use_pure_random = False


def run(request):
    event('preparing','Loading scene, camera and view layer')
    scene = bpy.data.scenes.get(request['scene']) if request['scene'] else bpy.context.scene
    if scene is None:
        raise ValueError(f"Scene not found: {request['scene']!r}")
    bpy.context.window.scene = scene
    layer = (scene.view_layers.get(request['view_layer']) if request['view_layer']
             else bpy.context.view_layer)
    if layer is None:
        raise ValueError(f"View layer not found: {request['view_layer']!r}")
    bpy.context.window.view_layer = layer
    for candidate in scene.view_layers:
        candidate.use = candidate == layer
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
        select_device(scene,request['execution'])
        if request['denoise'] is not None:
            scene.cycles.use_denoising = request['denoise']
        if request['noise_threshold'] is not None:
            scene.cycles.use_adaptive_sampling = request['noise_threshold'] > 0
            scene.cycles.adaptive_threshold = request['noise_threshold']
    else:
        if request['execution']['requested'] not in ('AUTO','CPU'):
            raise ValueError('Explicit GPU device selection requires CYCLES')
        request['execution'].update(backend='EEVEE',devices=[],fallback_reason=None)
        if request['denoise'] is not None or request['noise_threshold'] is not None:
            raise ValueError('Quality presets, denoise and noise_threshold currently require CYCLES')
        scene.eevee.taa_render_samples = request['samples']
    event('device','Using '+request['execution']['backend'])
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
    if request['style'] == 'sketch':
        sketch_style(scene, layer, request['dpi'])
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
    # Appended IDs retain source-library hints for future reuse. Their data are
    # already local; these hints are not dependencies of the rendered scene.
    # Clear only the in-memory hints, leaving actual linked libraries intact.
    for datablock in bpy.data.user_map():
        reference = datablock.library_weak_reference
        if reference:
            reference.filepath = ''
    dependencies = sorted({path for path in
        bpy.utils.blend_paths(absolute=True, packed=False, local=False) if path})
    dependency_hashes = {}
    for path in dependencies:
        paths = glob.glob(path.replace('<UDIM>', '[0-9][0-9][0-9][0-9]')) if '<UDIM>' in path else [path]
        if not paths: raise ValueError(f'Missing scene asset: {path}')
        for filename in paths:
            with open(filename,'rb') as stream:
                dependency_hashes[str(Path(filename).resolve())] = hashlib.file_digest(stream,'sha256').hexdigest()
    result = dict(scene=scene.name, camera=camera.name, view_layer=layer.name, frame=scene.frame_current,
                  execution=request['execution'],
                  style=request['style'],
                  width_mm=width, height_mm=height, pixels=pixels,
                  engine=scene.render.engine, blender=bpy.app.version_string,
                  sampling=(dict(samples=scene.cycles.samples, denoise=scene.cycles.use_denoising,
                      adaptive=scene.cycles.use_adaptive_sampling,
                      noise_threshold=scene.cycles.adaptive_threshold, device=scene.cycles.device)
                      if scene.render.engine == 'CYCLES' else dict(samples=scene.eevee.taa_render_samples)),
                  color_management=dict(view_transform=scene.view_settings.view_transform,
                      look=scene.view_settings.look, exposure=scene.view_settings.exposure,
                      gamma=scene.view_settings.gamma),
                  landmarks=anchors, dependencies=dependencies, dependency_hashes=dependency_hashes)
    stage = Path(request['output'])
    result['object_ids'] = prepare_passes(scene, layer, request['passes'], stage)
    scene.render.filepath = str(stage/'image.png')
    event('rendering','Rendering with '+request['execution']['backend'])
    bpy.ops.render.render(write_still=True, scene=scene.name)
    event('extracting','Collecting scene pixels and numeric passes')
    result['passes'] = collect_passes(request['passes'], stage, pixels) if request['passes'] else {}
    (stage/'scene.json').write_text(json.dumps(result, indent=2))


def inspect(request):
    scenes = []
    for scene in bpy.data.scenes:
        scenes.append(dict(name=scene.name, engine=scene.render.engine,
            camera=scene.camera.name if scene.camera else None,
            cameras=[dict(name=obj.name, type=obj.data.type, lens=obj.data.lens)
                     for obj in scene.objects if obj.type == 'CAMERA'],
            view_layers=[layer.name for layer in scene.view_layers],
            frame=scene.frame_current, frame_range=[scene.frame_start, scene.frame_end],
            resolution=[scene.render.resolution_x, scene.render.resolution_y],
            objects=[dict(name=obj.name, type=obj.type, hidden=obj.hide_render,
                collections=[collection.name for collection in obj.users_collection],
                materials=[slot.material.name for slot in obj.material_slots if slot.material])
                for obj in sorted(scene.objects, key=lambda obj: obj.name)]))
    result = dict(blender=bpy.app.version_string, scenes=scenes,
                  collections=sorted(collection.name for collection in bpy.data.collections))
    (Path(request['output']) / 'inventory.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
    inspect(request) if request.get('operation') == 'inspect' else run(request)
