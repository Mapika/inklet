"""Original instrumented laboratory cutaway; run inside Blender."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def main():
    source,output=map(Path,sys.argv[sys.argv.index('--')+1:])
    spec=importlib.util.spec_from_file_location('template_geometry',source)
    t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    m=dict(white=t.material('Porcelain',(.74,.76,.72),rough=.5),
        metal=t.material('Brushed steel',(.42,.49,.54),.75,.3),
        dark=t.material('Graphite',(.025,.041,.052),.25,.35),
        teal=t.material('Petrol enamel',(.015,.20,.19),.3,.3),
        blue=t.material('Coolant blue',(.025,.18,.35),.25,.25),
        amber=t.material('Amber fittings',(.62,.28,.055),.5,.28),
        floor=t.material('Warm floor',(.45,.43,.38),rough=.8),
        glass=t.material('Vessel glass',(.85,.94,.97),rough=.08,transmission=.8))
    t.box('Foundation',(0,0,-.16),(8.2,6.2,.3),m['white'])
    for x in range(8):
        for y in range(6):
            t.box('Floor tile',(-3.5+x,-2.5+y,.015),(.985,.985,.03),m['floor'],.003)
    t.box('Rear wall',(0,3.05,.60),(8.2,.15,1.2),m['white'])
    t.box('Window header',(0,3.05,3.15),(8.2,.15,.30),m['white'])
    for x in (-4,-2,0,2,4):
        t.box('Window mullion',(x,3.04,2.1),(.055,.10,1.8),m['metal'],.004)
    for x in (-4,4):
        t.box('Rear column',(x,3.04,1.65),(.18,.22,3.3),m['white'])

    def bench(name,x,y,w,d):
        t.box(name+' top',(x,y,.95),(w,d,.12),m['white'],.045)
        for dx in (-w/2+.15,w/2-.15):
            for dy in (-d/2+.12,d/2-.12):
                t.box(name+' leg',(x+dx,y+dy,.48),(.09,.09,.85),m['metal'],.01)
        t.box(name+' rail',(x,y,.31),(w-.18,d-.18,.08),m['metal'])
    bench('Process bench',0,1.65,6.6,1.3)
    bench('Analysis island',0,-1.25,3.8,1.45)
    for x in (-2.3,0,2.3):
        t.box('Under-bench cabinet',(x,1.70,.48),(1.40,.95,.76),m['teal'])
        for z in (.29,.55,.79):
            t.box('Drawer front',(x,1.205,z),(1.32,.035,.23),m['white'],.012)
            t.box('Drawer handle',(x,1.16,z+.035),(.45,.055,.035),m['metal'],.01)

    def reactor(x,name):
        t.cylinder(name+' lower collar',(x,1.55,1.11),.45,.16,m['metal'])
        t.cylinder(name+' fluid',(x,1.55,1.56),.385,.77,m['teal'])
        # Transmissive upper section leaves the liquid surface and probe visible.
        t.cylinder(name+' upper vessel',(x,1.55,2.04),.40,.25,m['glass'],.006)
        t.cylinder(name+' lid',(x,1.55,2.24),.46,.13,m['metal'])
        t.cylinder(name+' probe',(x,1.55,2.02),.04,.87,m['amber'])
        for k in range(8):
            a=math.tau*k/8
            t.cylinder(name+' bolt',(x+.40*math.cos(a),1.55+.40*math.sin(a),2.33),.035,.05,m['dark'],.004)
        for dx in (-.21,.21):
            t.cylinder(name+' port',(x+dx,1.55,2.43),.06,.24,m['amber'],.006)
        t.landmark('Target '+name,(x,1.12,1.85))
    reactor(-2.0,'Reactor A');reactor(-.7,'Reactor B')
    t.box('Feed pump',(1.10,1.50,1.27),(1.0,.78,.48),m['dark'],.06)
    for x in (.85,1.35):
        disk=t.cylinder('Pump head',(x,1.065,1.30),.18,.10,m['metal']);disk.rotation_euler.x=math.pi/2
    t.landmark('Target Feed pump',(1.10,1.01,1.30))
    t.box('Control display',(2.30,1.75,1.82),(1.10,.14,.70),m['dark'],.06)
    t.box('Display surface',(2.30,1.67,1.82),(.94,.025,.53),m['blue'],.02)
    t.box('Display stand',(2.30,1.80,1.28),(.07,.08,.58),m['metal'])
    t.landmark('Target Control display',(2.30,1.64,1.82))
    for n in range(7):
        t.box('Display trace',(1.96+n*.11,1.65,1.71+.07*math.sin(n)),(.075,.01,.018),m['amber'],.002)
    # Analysis island: 24 capped sample vials, a flow cell and a detector.
    t.box('Sample rack',(-.85,-1.25,1.07),(1.30,.82,.14),m['dark'])
    for x in range(6):
        for y in range(4):
            pos=(-1.37+x*.21,-1.55+y*.20)
            t.cylinder('Sample vial',(*pos,1.27),.065,.29,m['white'],.007)
            t.cylinder('Vial cap',(*pos,1.44),.073,.06,m['amber'],.006)
    t.landmark('Target Sample rack',(-.85,-1.62,1.37))
    t.box('Flow cell',(.53,-1.25,1.15),(.55,.65,.24),m['metal'])
    t.box('Flow cell window',(.53,-1.25,1.29),(.27,.34,.03),m['blue'],.02)
    t.landmark('Target Flow cell',(.53,-1.25,1.33))
    t.box('Optical detector',(1.35,-1.20,1.29),(.55,.72,.52),m['teal'],.045)
    lens=t.cylinder('Detector lens',(1.02,-1.20,1.34),.13,.16,m['dark']);lens.rotation_euler.y=math.pi/2
    t.landmark('Target Detector',(1.35,-1.58,1.34))

    # Floor-standing utilities and overhead services.
    for x in (-3.35,-2.78):
        t.cylinder('Gas bottle',(x,-.65,.91),.22,1.55,m['blue'],.11)
        t.cylinder('Gas valve',(x,-.65,1.78),.06,.18,m['amber'])
        gauge=t.cylinder('Pressure gauge',(x,-.76,1.91),.09,.04,m['white']);gauge.rotation_euler.x=math.pi/2
    t.landmark('Target Gas supply',(-3.35,-.88,1.12))
    t.box('Recirculator',(3.0,-1.15,.68),(1.08,1.10,1.22),m['teal'],.065)
    for n in range(9):
        t.box('Cooling grille',(3.0,-1.716,.36+n*.045),(.78,.025,.019),m['dark'],.003)
    t.box('Chiller display',(3.0,-1.72,1.03),(.56,.03,.23),m['blue'],.008)
    t.landmark('Target Recirculator',(3.0,-1.75,.83))
    for x in (-3.25,3.25):
        t.box('Gantry upright',(x,1.75,2.06),(.10,.12,2.2),m['metal'],.01)
        t.box('Gantry foot',(x,1.75,1.04),(.35,.30,.08),m['dark'])
    t.box('Overhead rail',(0,1.75,3.16),(6.70,.18,.14),m['metal'])
    for x in (-2,-.7):
        t.tube('Extraction riser',[(x,1.82,2.39),(x,2.28,2.62),(x,2.30,3.05)],.075,m['metal'])
    t.tube('Exhaust manifold',[(-2.2,2.30,3.05),(2.7,2.30,3.05),(3.55,2.8,3.05)],.12,m['metal'])
    t.landmark('Target Exhaust manifold',(.1,2.18,3.05))
    t.box('Cable tray',(0,.95,2.83),(6.2,.30,.07),m['dark'])
    for k in range(25):
        t.box('Tray rung',(-3+k*.25,.95,2.89),(.035,.29,.045),m['metal'],.004)
    t.landmark('Target Cable tray',(2.4,.79,2.88))
    for x in (-2,-.7,1.1,2.3):
        t.tube('Signal cable',[(x,1.55,2.42 if x<0 else 1.55),(x,.9,2.6),
            (x+.3,.9,2.97),(3,.9,2.97),(3,1.0,1.20)],.024,m['dark'])
    t.tube('Coolant supply',[(3,-1.1,1.29),(3,.3,.7),(2.5,1.0,1.1),
        (1.4,1.15,1.6),(-.49,1.55,2.52)],.035,m['blue'])
    t.tube('Feed transfer',[(-1.79,1.55,2.54),(-1.3,.65,2.70),(.85,.65,1.45),(1.1,1.02,1.35)],.032,m['amber'])
    t.tube('Analysis transfer',[(1.10,1.00,1.25),(1.10,.3,.72),(.53,-.6,.78),(.53,-.93,1.2)],.025,m['amber'])
    t.landmark('Target Transfer line',(-1.3,.65,2.70))
    t.landmark('Width left',(-4,-3,0));t.landmark('Width right',(4,-3,0))

    target=(0,0,1.35)
    scene=bpy.context.scene;scene.name='Instrumented laboratory'
    scene.camera=t.camera('Overview',(11,-15,12),target,12.2)
    t.camera('Process',(-5,-5,4.8),(-.5,1.5,1.75),5.1)
    t.camera('Analysis',(4,-7,5),(0,-1.25,1.12),5.4)
    for name,pos,power,size in [('Key',(1,-5,10),2200,7),('Fill',(-6,-2,6),1700,6),('Rim',(3,6,8),2300,5)]:
        bpy.ops.object.light_add(type='AREA',location=pos)
        lamp=bpy.context.object;lamp.name=name;lamp.data.energy=power;lamp.data.shape='DISK';lamp.data.size=size
        lamp.rotation_euler=(Vector(target)-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES';scene.cycles.samples=128;scene.cycles.use_denoising=True
    scene.render.resolution_x=1800;scene.render.resolution_y=1300
    scene.world=bpy.data.worlds.new('Studio');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.30,.34,.40,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.4
    scene.view_settings.view_transform='AgX';scene.unit_settings.system='METRIC'
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output.resolve()),compress=False)
    print(json.dumps(dict(objects=len(scene.objects),meshes=sum(o.type=='MESH' for o in scene.objects),
        curves=sum(o.type=='CURVE' for o in scene.objects))))


if __name__=='__main__':main()
