"""Original starter geometry. Executed only by Blender's Python."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def material(name, color, metal=0., rough=.35, transmission=0.):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    node = result.node_tree.nodes['Principled BSDF']
    node.inputs['Base Color'].default_value = (*color, 1)
    node.inputs['Metallic'].default_value = metal
    node.inputs['Roughness'].default_value = rough
    node.inputs['Transmission Weight'].default_value = transmission
    result.diffuse_color = (*color, 1)
    return result


def finish(obj, name, mat, bevel=0.):
    obj.name = name
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Edge radius', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        obj.modifiers.new('Surface normals', 'WEIGHTED_NORMAL')
    return obj


def box(name, pos, dims, mat, bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, mat, bevel)


def cylinder(name, pos, radius, height, mat, bevel=.02):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=radius, depth=height, location=pos)
    obj = finish(bpy.context.object, name, mat, bevel)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


def landmark(name, position):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_size = .12
    obj.location = position
    bpy.context.collection.objects.link(obj)


def tube(name, points, radius, mat):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    for point, position in zip(spline.bezier_points, points):
        point.co = position
        point.handle_left_type = point.handle_right_type = 'AUTO'
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    curve.materials.append(mat)


def camera(name, position, target, scale, kind='ORTHO'):
    bpy.ops.object.camera_add(location=position)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    obj.data.type = kind
    obj.data.ortho_scale = scale
    obj.data.lens = 50
    obj.data.clip_start = .01
    return obj


def laboratory(p, m):
    r, h, fraction = p['radius'], p['height'], p['fill_fraction']
    controller_x = r+1.15
    box('Bench', (.5,0,-.12), (5.7,3.5,.24), m['paper'])
    box('Vessel base', (0,0,.16), (2*r+.5,2*r+.5,.30), m['dark'])
    bottom = .4
    cylinder('Fluid', (0,0,bottom+h*fraction/2), r-.06, h*fraction, m['accent'])
    # A real annular wall, rather than a solid glass cylinder over the fluid.
    vertices, faces, count = [], [], 96
    for z, radius in ((bottom,r),(bottom+h,r),(bottom,r-.045),(bottom+h,r-.045)):
        vertices.extend((radius*math.cos(k*math.tau/count),radius*math.sin(k*math.tau/count),z)
                        for k in range(count))
    for k in range(count):
        j = (k+1)%count
        for a,b in ((0,count),(2*count,3*count),(count,3*count),(0,2*count)):
            face=(a+k,a+j,b+j,b+k)
            reverse = (a,b) in ((2*count,3*count),(0,2*count))
            faces.append(tuple(reversed(face)) if reverse else face)
    mesh = bpy.data.meshes.new('Vessel wall')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    wall = bpy.data.objects.new('Vessel',mesh)
    bpy.context.collection.objects.link(wall)
    finish(wall,'Vessel',m['glass'])
    for face in mesh.polygons:
        face.use_smooth = True
    for z in (bottom,bottom+h):
        cylinder('Vessel collar', (0,0,z), r+.10, .12, m['metal'])
    cylinder('Probe', (0,0,bottom+h*.6), .06, h*1.1, m['metal'])
    cylinder('Probe connector', (0,0,bottom+h+.25), .13, .24, m['gold'])
    box('Controller',(controller_x,0,.74),(1.05,1.1,1.15),m['dark'])
    box('Readout',(controller_x,-.565,.90),(.72,.035,.35),m['accent'],.015)
    dial = cylinder('Control dial',(controller_x,-.61,.49),.13,.10,m['metal'])
    dial.rotation_euler.x = math.pi/2
    tube('Probe cable',[(0,0,bottom+h+.37),(.3,.8,bottom+h+.55),
        (controller_x,.8,1.6),(controller_x,.3,1.35)],.035,m['dark'])
    landmark('Target vessel',(0,-r-.025,bottom+h*.45))
    landmark('Target probe',(0,0,bottom+h+.38))
    landmark('Target controller',(controller_x,-.60,.90))
    target = (.6,0,(bottom+h)/2)
    scale = 6.9
    camera('Overview',(7,-10,7),target,scale)
    camera('Detail',(-5,-7,5.5),(0,0,bottom+h*.5),scale,'PERSP')
    camera('Front',(.6,-12,target[2]),target,scale)
    return target, 1.


def product(p, m):
    w,d,h = p['width'],p['depth'],p['height']
    box('Studio plinth',(0,0,-.12),(w+1.4,d+1.3,.24),m['paper'],.10)
    box('Lower enclosure',(0,0,.17),(w,d,.22),m['dark'],.075)
    box('Enclosure',(0,0,.28+h/2),(w,d,h),m['accent'],.11)
    box('Top plate',(0,0,.31+h),(w-.08,d-.08,.10),m['metal'],.055)
    box('Display surround',(-w*.16,-d/2-.035,.28+h*.60),
        (w*.48,.06,h*.52),m['dark'],.035)
    box('Display',(-w*.16,-d/2-.075,.28+h*.60),
        (w*.42,.035,h*.40),m['screen'],.025)
    # Decorative display geometry is deliberately unlabelled; figure text is vector.
    for n in range(5):
        box('Display bar',(-w*.32+n*w*.065,-d/2-.095,.28+h*.55),
            (w*.035,.01,h*(.06+.03*n)),m['gold'],.003)
    dial = cylinder('Control dial',(w*.32,-d/2-.11,.28+h*.58),min(.22,h*.21),.18,m['metal'])
    dial.rotation_euler.x = math.pi/2
    for n in range(7):
        box('Top vent',(-w*.28+n*w*.09,d*.2,.365+h),(w*.035,d*.28,.014),m['dark'],.008)
    landmark('Target display',(-w*.16,-d/2-.10,.28+h*.60))
    landmark('Target control',(w*.32,-d/2-.21,.28+h*.58))
    landmark('Target enclosure',(w/2+.015,0,.28+h*.65))
    target=(0,0,(h+.35)/2)
    scale=max(w,d)*1.65+h*.5
    distance=max(w,d,h)*2.5
    camera('Overview',(distance,-distance*1.3,distance*.9),target,scale)
    camera('Detail',(distance*.7,-distance*1.2,distance*.55),target,scale,'PERSP')
    camera('Front',(0,-distance*2,target[2]),target,scale)
    return target, max(w,d)/2.8


def architecture(p, m):
    w,d,h = p['width'],p['depth'],p['height']
    box('Foundation',(0,0,-.13),(w+.2,d+.2,.26),m['paper'])
    strips=18
    for k in range(strips):
        box('Floor board',(-w/2+(k+.5)*w/strips,0,.025),(w/strips-.012,d,.05),m['wood'],.006)
    sill, top = h*.30, h*.88
    box('Rear sill',(0,d/2+.08,sill/2),(w+.16,.16,sill),m['paper'])
    box('Rear header',(0,d/2+.08,(top+h)/2),(w+.16,.16,h-top),m['paper'])
    for x in (-w/2,w/2):
        box('Window pier',(x,d/2+.08,(sill+top)/2),(.16,.16,top-sill),m['paper'])
    for x in (-w/3,0,w/3):
        box('Window mullion',(x,d/2+.05,(sill+top)/2),(.045,.11,top-sill),m['dark'],.005)
    for k in range(12):
        box('Timber screen',(-w/2-.04,-d/2+(k+.5)*d/12,h/2),(.08,.07,h),m['wood'],.006)
    box('Rug',(0,-d*.06,.07),(w*.70,d*.70,.03),m['rug'],.025)
    # Original furniture built from rounded cushions, arms and slender legs.
    for x in (-w*.20,w*.20):
        y=d*.13
        box('Chair seat',(x,y,.48),(.95,.88,.20),m['accent'],.09)
        box('Chair back',(x,y+.38,.86),(.95,.18,.77),m['accent'],.08)
        for side in (-1,1):
            box('Chair arm',(x+side*.46,y,.68),(.13,.84,.20),m['wood'],.055)
            for front in (-1,1):
                cylinder('Chair leg',(x+side*.36,y+front*.29,.24),.035,.38,m['dark'],.008)
    box('Table top',(0,-d*.24,.47),(w*.32,.70,.10),m['wood'],.06)
    for x in (-w*.12,w*.12):
        for y in (-d*.24-.23,-d*.24+.23):
            cylinder('Table leg',(x,y,.26),.03,.35,m['dark'],.006)
    box('Book',(.15,-d*.24,.56),(.35,.25,.065),m['gold'],.008)
    landmark('Target seating',(-w*.20,d*.13,.60))
    landmark('Target window',(0,d/2+.02,(sill+top)/2))
    landmark('Target table',(0,-d*.24,.53))
    landmark('Width left',(-w/2,-d/2,0))
    landmark('Width right',(w/2,-d/2,0))
    target=(0,0,h*.36)
    extent=max(w,d,h)
    scale=extent*1.6+h*.5
    camera('Overview',(extent*1.5,-extent*1.8,extent*1.3),target,scale)
    camera('Detail',(w*.85,-d*1.1,h*1.1),(0,d*.12,h*.38),scale,'PERSP')
    camera('Plan',(0,0,extent*3),(0,0,0),max(w,d*4/3)*1.2)
    return target, extent/4


def main():
    request=json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
    record=request['template']
    p=record['parameters']
    bpy.ops.wm.read_factory_settings(use_empty=True)
    print('INKLET_EVENT '+json.dumps(dict(phase='creating',message='Creating '+record['name']+' scene')),flush=True)
    rgb=[int(p['accent'][n:n+2],16)/255 for n in (1,3,5)]
    rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    m=dict(accent=material('Accent',rgb,rough=.28),
        dark=material('Graphite',(.022,.035,.044),.25,.30),
        metal=material('Satin aluminium',(.48,.55,.61),.78,.25),
        paper=material('Warm white',(.73,.72,.68),rough=.7),
        gold=material('Amber',(.60,.26,.065),.45,.30),
        wood=material('Oak',(.31,.17,.075),rough=.5),
        rug=material('Slate textile',(.18,.23,.23),rough=.95),
        screen=material('Display glass',(.025,.055,.065),rough=.20),
        glass=material('Clear vessel',(.85,.95,.98),rough=.07,transmission=.9))
    target,light_scale=globals()[record['name']](p,m)
    scene=bpy.context.scene
    scene.name=record['name'].title()
    scene.camera=scene.objects['Overview']
    scene.render.engine='CYCLES'
    scene.cycles.samples=64
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1200
    scene.render.resolution_y=900
    scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX'
    scene.world=bpy.data.worlds.new('Studio world')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.30,.34,.40,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
    for name,pos,power,size in [('Key',(1,-5,8),1400,5),('Fill',(-5,-1,4),900,4),('Rim',(3,5,7),1600,4)]:
        position=Vector(target)+Vector(pos)*light_scale
        bpy.ops.object.light_add(type='AREA',location=position)
        lamp=bpy.context.object
        lamp.name=name
        lamp.data.energy=power*light_scale**2
        lamp.data.shape='DISK'
        lamp.data.size=size*light_scale
        lamp.rotation_euler=(Vector(target)-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=record['metres_per_unit']
    record['blender']=bpy.app.version_string
    # This records the original recipe, not a claim that later edits match it.
    encoded=json.dumps(record,indent=2,sort_keys=True)
    scene['inklet_template']=encoded
    bpy.data.texts.new('inklet-template.json').write(encoded)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=request['output'],compress=False)


if __name__=='__main__':
    main()
