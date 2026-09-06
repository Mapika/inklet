"""Original showcase scenes, with one credited CC0 furniture asset.

Run inside Blender: --python blender_scenes.py -- KIND OUTPUT [CHAIR_BLEND].
"""
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def material(name, color, metal=0., rough=.3, emission=0.):
    m = bpy.data.materials.new(name); m.use_nodes = True
    shader = m.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metal
    shader.inputs['Roughness'].default_value = rough
    shader.inputs['Emission Color'].default_value = (*color, 1)
    shader.inputs['Emission Strength'].default_value = emission
    return m


def finish(obj, name, mat, bevel=0):
    obj.name = name; obj.data.materials.append(mat)
    for face in obj.data.polygons: face.use_smooth = True
    if bevel:
        mod = obj.modifiers.new('Edge radius', 'BEVEL'); mod.width = bevel; mod.segments = 3
        obj.modifiers.new('Normals', 'WEIGHTED_NORMAL')
    return obj


def box(name, pos, dims, mat, bevel=.035):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object; obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, bevel)


def ball(name, pos, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=radius, location=pos)
    return finish(bpy.context.object, name, mat)


def rod(name, a, b, radius, mat):
    a, b = Vector(a), Vector(b); delta = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=delta.length, location=(a+b)/2)
    obj = bpy.context.object
    obj.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
    return finish(obj, name, mat)


def tube(name, points, radius, mat):
    curve = bpy.data.curves.new(name, 'CURVE'); curve.dimensions = '3D'
    curve.bevel_depth = radius; curve.bevel_resolution = 4
    spline = curve.splines.new('POLY'); spline.points.add(len(points)-1)
    for point, xyz in zip(spline.points, points): point.co = (*xyz, 1)
    obj = bpy.data.objects.new(name, curve); bpy.context.collection.objects.link(obj)
    curve.materials.append(mat)
    return obj


def setup(kind):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene; scene.name = kind
    scene.render.engine = 'CYCLES'; scene.cycles.use_denoising = True
    scene.render.resolution_x = 1550; scene.render.resolution_y = 1030
    scene.world = bpy.data.worlds.new('Studio world'); scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.25,.29,.35,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .35
    scene.view_settings.view_transform = 'AgX'
    return scene


def camera(name, position, target, scale):
    bpy.ops.object.camera_add(location=position)
    cam = bpy.context.object; cam.name = name
    cam.rotation_euler = (Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = scale
    return cam


def lights(target):
    for name, pos, watts, size, color in (
        ('Key',(1,-5,9),1400,5,(1,.87,.72)),
        ('Fill',(-6,-1,5),1050,5,(.66,.83,1)),
        ('Rim',(3,5,7),1800,4,(1,1,1))):
        bpy.ops.object.light_add(type='AREA', location=pos)
        obj=bpy.context.object; obj.name=name; obj.data.energy=watts
        obj.data.shape='DISK'; obj.data.size=size; obj.data.color=color
        obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()


def photonics(m):
    box('Silicon substrate',(0,0,0),(5.4,3.4,.22),m['navy'])
    box('Oxide layer',(0,0,.14),(5.2,3.2,.08),m['white'])
    for y in (-.78,.78):
        tube('Bus waveguide',[(-2.6,y,.23),(2.6,y,.23)],.045,m['gold'])
        for x in (-1.1,1.1):
            points=[(x+.5*math.cos(t*math.tau/160),y*.35+.5*math.sin(t*math.tau/160),.23) for t in range(161)]
            tube('Ring resonator',points,.045,m['gold'])
    for y in (-.78,.78):
        tube('Optical fibre',[(-4.2+1.6*t/80,y-.45*math.sin(t*math.pi/80),.23) for t in range(81)],.085,m['teal'])
        rod('Fibre coupler',(-2.8,y,.23),(-2.4,y,.23),.13,m['silver'])
    for x in (-2.25,2.25):
        for y in (-1.25,1.25):box('Contact pad',(x,y,.24),(.35,.3,.06),m['gold'],.02)
    return ((7,-8,7),(-.45,0,.15),8.1)


def lattice(m):
    for z in range(3):
        for y in range(3):
            for x in range(3):
                centre=(x-1,y-1,z+.5)
                for dx in (-.5,.5):
                    for dy in (-.5,.5):
                        for dz in (-.5,.5):
                            rod('Lattice strut',centre,(centre[0]+dx,centre[1]+dy,centre[2]+dz),.055,m['teal'])
    for z in (-.15,3.15):box('Compression plate',(0,0,z),(3.5,3.5,.24),m['navy'])
    for z in (-.29,3.29):box('Load surface',(0,0,z),(2.8,2.8,.06),m['gold'])
    return ((7,-9,6),(0,0,1.5),8.8)


def helix(m):
    for offset, mat in ((0,m['teal']),(math.pi,m['orange'])):
        points=[]
        for k in range(401):
            t=k/400*math.tau*2.3
            points.append((.85*math.cos(t+offset),.85*math.sin(t+offset),k/400*4.8))
        tube('Helical backbone',points,.115,mat)
    for k in range(28):
        t=k/27*math.tau*2.3; z=k/27*4.8
        a=(.85*math.cos(t),.85*math.sin(t),z); b=(-a[0],-a[1],z)
        mid=(0,0,z)
        rod('Paired link',a,mid,.055,m['gold']); rod('Paired link',mid,b,.055,m['silver'])
        ball('Junction',a,.14,m['teal']); ball('Junction',b,.14,m['orange'])
    return ((7,-10,5),(0,0,2.4),8.5)


def architecture(m, chair):
    box('Foundation',(0,0,-.13),(5.6,4.7,.24),m['white'])
    for x in range(14):box('Oak floor',(x*.4-2.6,0,.015),(.39,4.5,.05),m['wood'],.008)
    # Open-front room with a broad rear window and a slatted side screen.
    box('Rear sill',(0,2.2,.5),(5.5,.16,1),m['white'])
    box('Rear header',(0,2.2,2.75),(5.5,.16,.3),m['white'])
    for x in (-2.6,2.6):box('Rear pier',(x,2.2,1.8),(.3,.16,1.6),m['white'])
    for x in (-1.7,0,1.7):box('Window mullion',(x,2.2,1.8),(.055,.12,1.6),m['navy'],.006)
    for k in range(12):box('Timber screen',(-2.7,-1.95+k*.36,1.45),(.08,.09,2.9),m['wood'],.01)
    box('Rug',(.15,-.2,.06),(3.7,2.8,.025),m['rug'],.025)
    with bpy.data.libraries.load(str(chair), link=False) as (source,dest):
        dest.objects=[name for name in source.objects if name=='modern_arm_chair_01']
    base=dest.objects[0]
    if base is None:raise ValueError('Expected Poly Haven modern_arm_chair_01 object')
    bpy.context.collection.objects.link(base)
    # Resolve external textures against the downloaded .blend before saving a new scene.
    for image in bpy.data.images:
        if image.source=='FILE' and image.filepath.startswith('//'):
            image.filepath=str((chair.parent/image.filepath[2:]).resolve())
    base.name='Lounge chair A';base.location=(-.95,.15,.085);base.rotation_euler.z=-.25
    second=base.copy();second.data=base.data.copy();bpy.context.collection.objects.link(second)
    second.name='Lounge chair B';second.location=(1.05,.45,.085);second.rotation_euler.z=.25
    box('Coffee table',(.15,-.95,.48),(1.7,.85,.1),m['wood'],.06)
    for x in (-.5,.8):
        for y in (-1.2,-.7):rod('Table leg',(x,y,.1),(x,y,.44),.035,m['navy'])
    box('Book',(.45,-.95,.57),(.4,.3,.07),m['teal'],.01)
    rod('Floor lamp',(2.15,1.3,.05),(2.15,1.3,2.1),.035,m['navy'])
    bpy.ops.mesh.primitive_cone_add(vertices=48,radius1=.35,radius2=.2,depth=.4,location=(2.15,1.3,2.05))
    finish(bpy.context.object,'Lamp shade',m['white'])
    return ((8,-10,8),(0,.1,1),10.8)


def main():
    args=sys.argv[sys.argv.index('--')+1:];kind=args[0];output=Path(args[1]).resolve()
    scene=setup(kind)
    m={
        'navy':material('Midnight enamel',(.016,.045,.08),.45,.25),
        'white':material('Warm plaster',(.78,.76,.71),0,.7),
        'gold':material('Satin gold',(.83,.43,.1),.78,.24),
        'silver':material('Aluminium',(.5,.61,.7),.8,.2),
        'teal':material('Turquoise',(.025,.48,.53),.5,.24),
        'orange':material('Coral',(.9,.15,.07),.35,.3),
        'wood':material('Oak',(.4,.22,.09),0,.5),
        'rug':material('Woven slate',(.18,.25,.3),0,.95),
    }
    pos,target,scale=(architecture(m,Path(args[2]).resolve()) if kind=='architecture'
                      else {'photonics':photonics,'lattice':lattice,'helix':helix}[kind](m))
    scene.camera=camera('Overview',pos,target,scale)
    camera('Detail',(pos[0]*.8,pos[1]*.8,pos[2]),target,scale*.7)
    lights(target)
    if kind=='architecture':bpy.ops.file.pack_all()
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


if __name__=='__main__':main()
