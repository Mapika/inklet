"""Original sensor housing for the dev4 vector-path example; run inside Blender."""
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, color, *, metallic=0, roughness=.35):
    result=bpy.data.materials.new(name);result.use_nodes=True
    node=result.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value=(*color,1)
    node.inputs['Metallic'].default_value=metallic
    node.inputs['Roughness'].default_value=roughness
    return result


def cylinder(name, radius, depth, z, mat, *, x=0, y=0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=radius,depth=depth,location=(x,y,z))
    obj=bpy.context.object;obj.name=name;obj.data.materials.append(mat)
    bevel=obj.modifiers.new('Machined edges','BEVEL');bevel.width=.045;bevel.segments=3
    obj.modifiers.new('Surface normals','WEIGHTED_NORMAL')
    for polygon in obj.data.polygons:polygon.use_smooth=True
    return obj

body=material('Deep teal ceramic',(.025,.20,.18),roughness=.24)
metal=material('Satin aluminium',(.46,.53,.55),metallic=.8,roughness=.27)
base=material('Graphite mount',(.055,.075,.085),metallic=.25)
accent=material('Amber connector',(.65,.25,.045),metallic=.4)
cylinder('Sensor body',.83,2.45,1.55,body)
cylinder('Lower collar',1.03,.18,.40,metal)
cylinder('Upper collar',1.03,.18,2.80,metal)
cylinder('Base',1.46,.22,.17,base)
cylinder('Top cap',.79,.17,2.96,body)
for n in range(4):
    angle=math.pi/4+n*math.pi/2
    x,y=1.20*math.cos(angle),1.20*math.sin(angle)
    cylinder('Mount screw '+str(n),.095,.08,.32,metal,x=x,y=y)
for n,x in enumerate((-.26,.26)):
    cylinder('Connector '+str(n),.13,.29,3.13,accent,x=x)

scene=bpy.context.scene
for name,position,power,size in [('Key',(2,-4,7),1100,5),('Fill',(-4,-1,4),750,4),('Rim',(2,5,5),1300,3)]:
    bpy.ops.object.light_add(type='AREA',location=position)
    lamp=bpy.context.object;lamp.name=name;lamp.data.energy=power;lamp.data.shape='DISK';lamp.data.size=size
    lamp.rotation_euler=(Vector((0,0,1.4))-lamp.location).to_track_quat('-Z','Y').to_euler()
for name,kind,position in [('Overview','ORTHO',(6,-8,5.5)),('Perspective','PERSP',(6,-8,5.5))]:
    bpy.ops.object.camera_add(location=position)
    cam=bpy.context.object;cam.name=name;cam.data.type=kind;cam.data.ortho_scale=5.3;cam.data.lens=58
    cam.rotation_euler=(Vector((0,0,1.55))-cam.location).to_track_quat('-Z','Y').to_euler()
scene.camera=scene.objects['Overview'];scene.render.engine='CYCLES'
scene.render.resolution_x=850;scene.render.resolution_y=780
scene.world=bpy.data.worlds.new('Studio world');scene.world.color=(.22,.22,.22)
scene.view_settings.view_transform='AgX'
output=Path(sys.argv[-1]).resolve();output.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
