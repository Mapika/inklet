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
for name,pos in (('Front',(0,-7,0)),('Side',(5,-7,3)),('Perspective',(0,-7,0))):
 bpy.ops.object.camera_add(location=pos);cam=bpy.context.object;cam.name=name
 cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=5
 if name=='Perspective':cam.data.type='PERSP';cam.data.shift_x=.08;cam.data.shift_y=-.04
bpy.ops.object.light_add(type='AREA',location=(0,-4,5));lamp=bpy.context.object
lamp.data.energy=500;lamp.rotation_euler=(Vector((0,0,0))-lamp.location).to_track_quat('-Z','Y').to_euler()
scene=bpy.context.scene;scene.camera=scene.objects['Front'];scene.render.engine='CYCLES'
scene.render.resolution_x=200;scene.render.resolution_y=100;scene.view_settings.view_transform='Standard'
collection=bpy.data.collections.new('Geometry');scene.collection.children.link(collection)
for owner in list(obj.users_collection):owner.objects.unlink(obj)
collection.objects.link(obj)
empty=scene.view_layers.new('Empty');empty.layer_collection.children['Geometry'].exclude=True
scene.use_nodes=True
output=scene.node_tree.nodes.new('CompositorNodeOutputFile');output.base_path=sys.argv[-1]+'.forbidden'
scene.node_tree.links.new(scene.node_tree.nodes.get('Render Layers').outputs['Image'],output.inputs[0])
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])
''')
    subprocess.run([str(find_blender().path),'--background','--factory-startup','--python-exit-code','1','--python',str(script),
                    '--',str(texture),str(path)],check=True,capture_output=True,timeout=60)
    return path


def options(scene_file):
    return dict(width=50,dpi=60,samples=2,device='CPU',cache=scene_file.parent/'cache',
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


def test_numeric_passes_orientation_units_masks_and_cache(scene_file):
    import numpy as np
    from io import BytesIO
    from PIL import Image
    opts=options(scene_file)
    opts.update(passes=('normal','object_id','depth'), bindings={'Sample':{'location':[0,0,.5]}})
    before=scene_file.read_bytes()
    result=i.render_blend(scene_file,**opts)
    beauty=i.render_blend(scene_file,**{k:v for k,v in opts.items() if k!='passes'})
    a=np.array(Image.open(BytesIO(beauty.diagram.prim.data)),dtype=int)
    b=np.array(Image.open(BytesIO(result.diagram.prim.data)),dtype=int)
    assert np.abs(a-b).max()<=1  # Extracting data must preserve the beauty render.
    depth=result.passes['depth'];normal=result.passes['normal'];ids=result.passes['object_id']
    w,h=depth.pixels
    assert depth.value(w//2,h//2)==pytest.approx(6,abs=.01)
    assert normal.value(w//2,h//2)==pytest.approx((0,-1,0),abs=.001)
    assert ids.value(w//2,h//2)==result.metadata['object_ids']['Sample']
    assert depth.value(0,0)==pytest.approx(1e10)
    mask=ids.to_numpy()>0
    assert np.where(mask)[0].mean()<h/2-3  # +Z is upwards in the output image
    assert not depth.to_numpy().flags.writeable
    with pytest.raises(TypeError):result.passes['depth']=None
    stencil=result.object_mask('Sample')
    assert stencil.bbox==result.diagram.bbox
    assert stencil.anchor_point('origin')==result.diagram.anchor_point('origin')
    assert i.render_blend(scene_file,**opts).cache_hit
    assert not scene_file.with_suffix('.blend.forbidden').exists()
    assert scene_file.read_bytes()==before
    cached=opts['cache']/'scenes'/result.metadata['cache_key']/'depth.f32'
    cached.write_bytes(b'corrupt')
    rebuilt=i.render_blend(scene_file,**opts)
    assert not rebuilt.cache_hit
    assert rebuilt.passes['depth'].data==depth.data
    assert depth.value(w//2,h//2)==pytest.approx(6,abs=.01)
    npy=scene_file.parent/'depth.npy';depth.save(npy)
    assert np.array_equal(np.load(npy),depth.to_numpy())


def test_view_layer_selection_and_errors(scene_file):
    from PIL import Image
    from io import BytesIO
    opts=options(scene_file);opts['landmarks']={}
    result=i.render_blend(scene_file,**opts,view_layer='Empty',passes=('object_id',))
    assert result.metadata['view_layer']=='Empty'
    assert not result.passes['object_id'].to_numpy().any()
    assert Image.open(BytesIO(result.diagram.prim.data)).getchannel('A').getextrema()==(0,0)
    with pytest.raises(BlenderError,match='View layer not found'):
        i.render_blend(scene_file,**opts,view_layer='Missing')
    with pytest.raises(ValueError,match='sequence'):
        i.render_blend(scene_file,**opts,passes='depth')
    with pytest.raises(ValueError,match='must not repeat'):
        i.render_blend(scene_file,**opts,passes=('depth','depth'))


def test_inspection_and_quality_settings_are_explicit(scene_file):
    original=scene_file.read_bytes()
    inventory=i.inspect_blend(scene_file)
    scene=inventory['scenes'][0]
    assert {c['name'] for c in scene['cameras']}=={'Front','Side','Perspective'}
    assert 'Empty' in scene['view_layers']
    assert next(o for o in scene['objects'] if o['name']=='Sample')['materials']==['Authored material']
    assert inventory['sha256']==hashlib.sha256(original).hexdigest()
    result=i.render_blend(scene_file,**options(scene_file),quality='final',denoise=False,noise_threshold=0)
    assert result.metadata['request']['quality']=='final'
    assert result.metadata['sampling']['samples']==2
    assert result.metadata['sampling']['denoise'] is False
    assert result.metadata['sampling']['adaptive'] is False
    assert result.metadata['pixels'][0]==118  # explicit DPI=60 wins over final=300
    assert scene_file.read_bytes()==original


def test_sketch_style_changes_surface_render_without_saving_source(scene_file):
    opts=options(scene_file)
    original=scene_file.read_bytes()
    authored=i.render_blend(scene_file,**opts)
    sketch=i.render_blend(scene_file,**opts,style='sketch',quality='draft')
    assert sketch.metadata['style']=='sketch'
    assert sketch.diagram.prim.data!=authored.diagram.prim.data
    assert sketch.diagram.bbox==authored.diagram.bbox
    assert i.render_blend(scene_file,**opts,style='sketch',quality='draft').cache_hit
    assert scene_file.read_bytes()==original
    # Authored Freestyle switches must not disable or rescale the sketch preset.
    alternate=scene_file.parent/'freestyle-off.blend'
    script=scene_file.parent/'freestyle-off.py'
    script.write_text('''import bpy,sys
for layer in bpy.context.scene.view_layers:layer.use_freestyle=False
bpy.context.scene.render.line_thickness_mode='RELATIVE'
bpy.context.scene.render.line_thickness=5
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])
''')
    subprocess.run([str(find_blender().path),'--background','--factory-startup','--disable-autoexec',
                    str(scene_file),'--python-exit-code','1','--python',str(script),'--',str(alternate)],
                   check=True,capture_output=True,timeout=60)
    overridden=i.render_blend(alternate,**opts,style='sketch',quality='draft')
    from io import BytesIO
    from PIL import Image
    # Blender also embeds filenames and render timings in the PNG metadata.
    assert (Image.open(BytesIO(overridden.diagram.prim.data)).tobytes()
            ==Image.open(BytesIO(sketch.diagram.prim.data)).tobytes())
    with pytest.raises(ValueError,match='style'):i.render_blend(scene_file,**opts,style='unknown')


def test_packed_appended_scene_does_not_require_its_original_library(scene_file,tmp_path):
    library=tmp_path/'source.blend';portable=tmp_path/'portable.blend'
    script=tmp_path/'append.py'
    script.write_text('''import bpy,sys
original,library,portable=sys.argv[-3:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add();bpy.context.object.name='Appended cube'
bpy.ops.wm.save_as_mainfile(filepath=library)
bpy.ops.wm.open_mainfile(filepath=original)
with bpy.data.libraries.load(library,link=False) as (source,dest):
 dest.objects=['Appended cube']
obj=dest.objects[0];bpy.context.scene.collection.objects.link(obj);obj.hide_render=True
assert any(i.library_weak_reference for i in bpy.data.user_map())
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=portable)
''')
    subprocess.run([str(find_blender().path),'--background','--factory-startup','--disable-autoexec',
                    '--python-exit-code','1','--python',str(script),'--',str(scene_file),str(library),str(portable)],
                   check=True,capture_output=True,timeout=60)
    library.unlink()
    original=portable.read_bytes()
    rendered=i.render_blend(portable,**options(scene_file),quality='draft')
    assert rendered.diagram.prim.data.startswith(b'\x89PNG')
    assert portable.read_bytes()==original


def test_queued_identical_renders_share_work_and_report_cache_hits(scene_file,tmp_path):
    opts=options(scene_file)|{'cache':tmp_path/'cache'}
    events=[]
    with i.RenderQueue(max_workers=2) as queue:
        jobs=[queue.submit(scene_file,**opts,progress=events.append) for _ in range(2)]
        results=[job.result(30) for job in jobs]
    assert sorted(result.cache_hit for result in results)==[False,True]
    assert sum(event.phase=='starting' for event in events)==1
    assert results[0].diagram.prim.data==results[1].diagram.prim.data
    assert all(job.progress.phase=='complete' for job in jobs)


def test_cancelled_blender_render_never_commits_incomplete_cache(scene_file,tmp_path):
    import threading
    cancel=threading.Event();events=[]
    def progress(event):
        events.append(event)
        if event.phase=='rendering':cancel.set()
    opts=options(scene_file)|{'cache':tmp_path/'cache'}
    with pytest.raises(i.RenderCancelled):
        i.render_blend(scene_file,**opts,progress=progress,cancel=cancel)
    assert any(event.phase=='rendering' for event in events)
    assert not list((tmp_path/'cache').rglob('manifest.json'))
    assert not list((tmp_path/'cache').rglob('.render-*'))
    assert not i.render_blend(scene_file,**opts).cache_hit


def test_auto_cpu_fallback_is_recorded_and_explicit_cpu_remains_available(scene_file,monkeypatch):
    from inklet.three import devices
    monkeypatch.setattr(devices,'_inventory',lambda *a,**k:{'backends':{}})
    opts=options(scene_file);opts.pop('device')
    result=i.render_blend(scene_file,**opts)
    assert result.metadata['execution']['requested']=='AUTO'
    assert result.metadata['execution']['backend']=='CPU'
    assert result.metadata['execution']['fallback_reason']
    explicit=i.render_blend(scene_file,**opts,device='CPU')
    assert explicit.metadata['cache_key']!=result.metadata['cache_key']
    with pytest.raises(BlenderError,match='No matching'):
        i.render_blend(scene_file,**opts,fallback='error')


def test_available_gpu_renders_numeric_passes_without_cpu_fallback(scene_file):
    inventory=i.render_devices()
    backend=next((name for name,info in inventory['backends'].items() if info['devices']),None)
    if backend is None:pytest.skip('No Cycles GPU device available')
    selected=inventory['backends'][backend]['devices'][0]['id']
    opts=options(scene_file)|dict(device=backend,devices=[selected],fallback='error',
                                 passes=('depth','normal','object_id'))
    gpu=i.render_blend(scene_file,**opts)
    assert gpu.metadata['sampling']['device']=='GPU'
    assert gpu.metadata['execution']['backend']==backend
    assert [d['id'] for d in gpu.metadata['execution']['devices']]==[selected]
    assert gpu.passes['normal'].channels==3
    assert gpu.passes['object_id'].value(59,29)>0
    cpu=i.render_blend(scene_file,**(opts|dict(device='CPU',devices=None)))
    assert cpu.metadata['cache_key']!=gpu.metadata['cache_key']
    assert cpu.passes['depth'].value(59,29)==pytest.approx(gpu.passes['depth'].value(59,29),rel=1e-5)
    assert i.render_blend(scene_file,**opts).cache_hit


@pytest.mark.parametrize('camera', ['Front','Side','Perspective'])
def test_saved_camera_projects_like_blender_and_depth_hides_interior(scene_file, camera):
    opts=options(scene_file)
    opts.update(camera=camera,passes=('depth',),dpi=120,
                landmarks={'test':[.4,-1,.3],'centre':[0,0,0],'outside':[0,-2,0]})
    result=i.render_blend(scene_file,**opts)
    for name,world in (('test',[.4,-1,.3]),('centre',[0,0,0]),('outside',[0,-2,0])):
        projected=result.project(world)
        authored=result.diagram.anchor_point(name)
        assert projected.point.x==pytest.approx(authored.x,abs=1e-4)
        assert projected.point.y==pytest.approx(authored.y,abs=1e-4)
    assert result.project([0,0,0]).visible is False
    assert result.project([0,-2,0]).visible is True
    # The camera is saved in the snapshot: projection remains usable offline.
    layer=result.path3d([[-3,0,0],[3,0,0]],stroke='#d85e45',stroke_width=.3)
    assert layer.notes['scene_overlay']['visible_runs']>=2
    assert layer.notes['scene_overlay']['hidden_runs']>=1
    assert layer.width==result.diagram.width
    assert layer.height==result.diagram.height


def test_perspective_depth_is_axial_at_an_off_axis_surface(scene_file):
    opts=options(scene_file);opts.update(camera='Perspective',passes=('depth',),dpi=150)
    result=i.render_blend(scene_file,**opts)
    point=result.project([.7,-1,.3])
    depth=result.passes['depth']
    px=int((point.point.x/result.diagram.width+.5)*depth.pixels[0])
    py=int((point.point.y/result.diagram.height+.5)*depth.pixels[1])
    assert depth.value(px,py)==pytest.approx(point.depth,abs=.012)
