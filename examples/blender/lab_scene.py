"""Author a reusable laboratory .blend scene. Run with Blender --background --python.

The optional argument after -- is the destination .blend path. All geometry and
materials are procedural and original to Inklet; no downloaded assets are used.
"""
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def material(name, color, metallic=0., roughness=.35, transmission=0.):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    shader=m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Metallic'].default_value=metallic
    shader.inputs['Roughness'].default_value=roughness
    shader.inputs['Transmission Weight'].default_value=transmission
    return m

metal=material('Brushed aluminium',(.45,.52,.58),.8,.25)
navy=material('Instrument housing',(.025,.075,.12),.3,.28)
blue=material('Sample fluid',(.01,.32,.5),.05,.18,.2)
glass=material('Borosilicate',(.82,.94,.97),0,.08,.88)
orange=material('Electrode coating',(.9,.24,.04),.25,.25)
white=material('Bench',(.72,.77,.81),0,.65)
black=material('Rubber',(.015,.02,.025),0,.7)

def finish(obj,name,mat):
    obj.name=name;obj.data.materials.append(mat)
    bevel=obj.modifiers.new('Manufactured edges','BEVEL');bevel.width=.055;bevel.segments=3
    obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return obj

def box(name,position,size,mat):
    bpy.ops.mesh.primitive_cube_add(size=1,location=position);obj=bpy.context.object
    obj.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(obj,name,mat)

def cylinder(name,position,radius,depth,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=radius,depth=depth,location=position)
    obj=finish(bpy.context.object,name,mat)
    for face in obj.data.polygons:face.use_smooth=True
    return obj

box('Bench',(0,0,-.2),(8,6,.3),white)
box('Base',(0,0,.1),(3.4,2.8,.3),navy)
for x in (-1.25,1.25):
 for y in (-.95,.95):cylinder('Foot',(x,y,-.02),.2,.24,black)
# An open glass vessel built as an annular mesh, with a distinct fluid volume.
verts=[];faces=[];n=96
for z,r in ((.4,1.),(2.35,1.),(.4,.94),(2.35,.94)):
 verts.extend((r*math.cos(k*math.tau/n),r*math.sin(k*math.tau/n),z) for k in range(n))
for k in range(n):
 j=(k+1)%n
 for a,b in ((0,n),(2*n,3*n),(n,3*n),(0,2*n)):faces.append((a+k,a+j,b+j,b+k))
mesh=bpy.data.meshes.new('Vessel mesh');mesh.from_pydata(verts,[],faces);mesh.update()
obj=bpy.data.objects.new('Chamber',mesh);bpy.context.collection.objects.link(obj);obj.data.materials.append(glass)
for face in mesh.polygons:face.use_smooth=True
cylinder('Fluid',(0,0,1.03),.92,1.22,blue)
cylinder('Lid',(0,0,2.4),1.08,.16,metal)
cylinder('Bottom ring',(0,0,.38),1.07,.14,metal)
for x in (-.42,.42):
 cylinder('Electrode' if x < 0 else 'Reference',(x,0,1.65),.095,2.,orange if x < 0 else metal)
 cylinder('Connector',(x,0,2.72),.17,.2,black)
box('Controller',(2.,.2,.85),(1.1,1.55,1.4),navy)
box('Display',(2.,-.595,1.12),(.8,.03,.42),blue)
for x in (1.75,2.05,2.3):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.075,location=(x,-.63,.65))
 finish(bpy.context.object,'Control button',orange)
for x in (-.42,.42):
 curve=bpy.data.curves.new('Cable','CURVE');curve.dimensions='3D';curve.bevel_depth=.045;curve.bevel_resolution=3
 spline=curve.splines.new('BEZIER');spline.bezier_points.add(3)
 for p,co in zip(spline.bezier_points,((x,0,2.82),(x,1.,3.1),(2.,1.,2.5),(2.,.5,1.58))):
  p.co=co;p.handle_left_type=p.handle_right_type='AUTO'
 obj=bpy.data.objects.new('Cable',curve);bpy.context.collection.objects.link(obj);curve.materials.append(black)

def camera(name,position,target,lens):
 bpy.ops.object.camera_add(location=position);obj=bpy.context.object;obj.name=name
 obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler();obj.data.lens=lens
 return obj
cam=camera('Overview',(7,-10,7),(.55,0,1.25),52)
camera('Detail',(-4.8,-6.5,4.6),(0,0,1.45),62)
for name,pos,power,size in (('Key',(1,-4,8),1100,5),('Fill',(-4,-1,4),750,4),('Rim',(2,5,6),1400,3)):
 bpy.ops.object.light_add(type='AREA',location=pos);lamp=bpy.context.object;lamp.name=name
 lamp.data.energy=power;lamp.data.shape='DISK';lamp.data.size=size
 lamp.rotation_euler=(Vector((0,0,1))-lamp.location).to_track_quat('-Z','Y').to_euler()
scene=bpy.context.scene;scene.name='Laboratory';scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=32
scene.world.color=(.2,.2,.2);scene.render.resolution_x=900;scene.render.resolution_y=650
scene.view_settings.view_transform='AgX'
path=Path(sys.argv[sys.argv.index('--')+1]) if '--' in sys.argv else Path('out/lab-scene.blend')
path=path.resolve();path.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path))
