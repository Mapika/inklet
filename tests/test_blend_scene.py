"""Actual .blend integration: cameras, provenance, cache and live bindings."""
import hashlib
import subprocess

import pytest
import inklet as i
from inklet.three.blender import blender_available, find_blender, BlenderError
from inklet.three.scenes import _bindings, _landmarks


def test_scene_options_reject_ambiguous_bindings():
    with pytest.raises(ValueError):_bindings({'Cube':{'script':'bad'}})
    with pytest.raises(ValueError):_bindings({'Cube':{'location':[1,2]}})
    with pytest.raises(ValueError):_landmarks({'point':{'object':'Cube'}})
    with pytest.raises(ValueError):i.render_blend('missing.blend',width=50)


@pytest.fixture(scope='module')
def scene_file(tmp_path_factory):
    if not blender_available():pytest.skip('Blender integration requires Blender 4.2+')
    from PIL import Image
    folder=tmp_path_factory.mktemp('blend-scene');path=folder/'authored.blend'
    texture=folder/'texture.png';Image.new('RGB',(8,8),'#aa3311').save(texture)
    script=folder/'create.py'
    script.write_text('''import bpy,sys
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add()
obj=bpy.context.object;obj.name='Sample'
mat=bpy.data.materials.new('Authored material');mat.use_nodes=True
tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(sys.argv[-2])
mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
obj.data.materials.append(mat)
for name,pos in (('Front',(0,-7,0)),('Side',(5,-7,3))):
 bpy.ops.object.camera_add(location=pos);cam=bpy.context.object;cam.name=name
 cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=5
bpy.ops.object.light_add(type='AREA',location=(0,-4,5));lamp=bpy.context.object
lamp.data.energy=500;lamp.rotation_euler=(Vector((0,0,0))-lamp.location).to_track_quat('-Z','Y').to_euler()
scene=bpy.context.scene;scene.camera=scene.objects['Front'];scene.render.engine='CYCLES'
scene.render.resolution_x=200;scene.render.resolution_y=100;scene.view_settings.view_transform='Standard'
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])
''')
    subprocess.run([str(find_blender().path),'--background','--factory-startup','--python',str(script),
                    '--',str(texture),str(path)],check=True,capture_output=True,timeout=60)
    return path


def options(scene_file):
    return dict(width=50,dpi=60,samples=2,cache=scene_file.parent/'cache',
                landmarks={'origin':'Sample','surface':{'object':'Sample','point':[0,-1,0]}},camera='Front')


def test_scene_preserves_file_and_projects_anchors(scene_file):
    before=hashlib.sha256(scene_file.read_bytes()).hexdigest()
    result=i.render_blend(scene_file,**options(scene_file))
    assert result.diagram.width==50 and result.diagram.height==25
    assert result.diagram.anchor_point('origin').x==pytest.approx(0,abs=1e-5)
    assert result.diagram.anchor_point('origin').y==pytest.approx(0,abs=1e-5)
    assert result.metadata['camera']=='Front'
    assert result.metadata['landmarks']['surface']['in_frame']
    assert hashlib.sha256(scene_file.read_bytes()).hexdigest()==before
    assert result.diagram.prim.data.startswith(b'\x89PNG')
    assert i.render_blend(scene_file,**options(scene_file)).cache_hit
    assert any(d['path'].endswith('texture.png') for d in result.metadata['dependencies'])


def test_changed_external_asset_invalidates_render(scene_file):
    from PIL import Image
    before=i.render_blend(scene_file,**options(scene_file))
    Image.new('RGB',(8,8),'#2255cc').save(scene_file.parent/'texture.png')
    after=i.render_blend(scene_file,**options(scene_file))
    assert not after.cache_hit
    assert after.diagram.prim.data != before.diagram.prim.data
    assert before.metadata['image_sha256'] != after.metadata['image_sha256']


def test_live_scene_binding_rebuilds_and_snapshot_keeps_pixels(scene_file):
    data=i.dataset({'x':[0.]},name='scene positions',source=i.Source('Test','simulated'))
    location=i.derive(lambda values:[values[0],0,0],data.column('x'))
    opts=options(scene_file);opts['bindings']={'Sample':{'location':location}}
    spec=i.blend_scene_spec(scene_file,**opts)
    doc=i.document(width=60);doc.add('scene',spec)
    first=doc.compile();svg=first.to_svg()
    assert first.metadata['rendering']['scenes'][0]['camera']=='Front'
    data.update(x=[.7])
    second=doc.compile()
    assert first.to_svg()==svg and second.to_svg()!=svg
    assert second.metadata['rendering']['scenes'][0]['landmarks']['origin']['x_mm'] > 26
    assert second.metadata['datasets'][0]['name']=='scene positions'


def test_named_camera_and_failure_are_explicit(scene_file):
    opts=options(scene_file);opts['camera']='Side'
    result=i.render_blend(scene_file,**opts)
    assert result.metadata['camera']=='Side'
    opts['camera']='Missing'
    with pytest.raises(BlenderError,match='camera'):i.render_blend(scene_file,**opts)


def test_colour_binding_overrides_linked_texture_and_invalidates(scene_file):
    opts=options(scene_file)
    before=i.render_blend(scene_file,**opts)
    after=i.render_blend(scene_file,**opts,bindings={'Sample':{'color':'#00ff00'}})
    assert after.diagram.prim.data != before.diagram.prim.data
    assert after.metadata['request']['bindings']['Sample']['color']==[0.,1.,0.,1.]


def test_corrupt_cache_and_missing_asset_are_not_reused(scene_file):
    opts=options(scene_file)
    before=i.render_blend(scene_file,**opts)
    cached=opts['cache']/'scenes'/before.metadata['cache_key']/'image.png'
    cached.write_bytes(b'broken')
    assert not i.render_blend(scene_file,**opts).cache_hit
    asset=scene_file.parent/'texture.png';data=asset.read_bytes();asset.unlink()
    try:
        with pytest.raises(BlenderError,match='texture.png'):i.render_blend(scene_file,**opts)
    finally:asset.write_bytes(data)
