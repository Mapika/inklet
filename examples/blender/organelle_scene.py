"""Render calibrated segmentation meshes without geometrical exaggeration."""
import importlib.util
from itertools import product
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def main():
    helper,folder,output=map(Path,sys.argv[sys.argv.index('--')+1:])
    spec=importlib.util.spec_from_file_location('geometry',helper)
    t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
    record=json.loads((folder/'meshes.json').read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials={name:t.material(name,color,rough=.45) for name,color in record['colors'].items()}
    for item in record['meshes']:
        bpy.ops.wm.obj_import(filepath=str(folder/item['file']),forward_axis='Y',up_axis='Z')
        obj=bpy.context.selected_objects[0];obj.name=item['name'];obj.data.materials.clear()
        if any(abs(obj.matrix_world[r][c]-(1 if r==c else 0))>1e-8 for r in range(4) for c in range(4)):
            raise RuntimeError('OBJ import changed calibrated world coordinates')
        obj.data.materials.append(materials[item['material']])
        for face in obj.data.polygons:face.use_smooth=True
    bounds=record['bounds_xyz'];centre=Vector([(a+b)/2 for a,b in zip(*bounds)])
    t.camera('Overview',centre+Vector((14,-55,19)),centre,45)
    scene=bpy.context.scene;scene.camera=bpy.data.objects['Overview']
    # Fit the entire calibrated crop at the recipe's 280:175 image aspect.
    # Blender's landscape orthographic scale is the horizontal field width.
    rotation=scene.camera.rotation_euler.to_matrix().transposed()
    corners=[rotation@(Vector(p)-scene.camera.location) for p in product(*zip(*bounds))]
    scene.camera.data.ortho_scale=1.10*max(
        2*max(abs(p.x) for p in corners),
        (280/175)*2*max(abs(p.y) for p in corners))
    # Select actual mesh surface points from the camera direction. These are
    # label anchors, not substitute centroids for the quantitative report.
    depsgraph=bpy.context.evaluated_depsgraph_get()
    for item in record['anchors']:
        obj=bpy.data.objects[item['object']]
        target=Vector(item['centroid_xyz']);direction=(target-scene.camera.location).normalized()
        tree=BVHTree.FromObject(obj,depsgraph)
        hit=tree.ray_cast(scene.camera.location,direction)[0]
        # A curved organelle's centroid can lie outside its mask. Use the
        # nearest actual mesh surface if the centroid ray misses the object.
        if hit is None:hit=tree.find_nearest(target)[0]
        if hit is None:raise RuntimeError('No surface anchor for '+item['id'])
        # Prefer a genuinely exposed point on this same object. A nearest
        # centroid point can be behind ER or another mitochondrial branch.
        candidates=[]
        faces=obj.data.polygons
        for index in range(0,len(faces),max(1,len(faces)//512)):
            point=faces[index].center
            ray=(point-scene.camera.location).normalized()
            found,location,_,_,owner,_=scene.ray_cast(depsgraph,scene.camera.location,ray)
            if found and owner.original==obj:
                candidates.append(location)
        if candidates:hit=min(candidates,key=lambda p:(p-target).length_squared)
        t.landmark('Target '+item['id'],hit)
    scene.render.engine='CYCLES';scene.cycles.samples=256;scene.cycles.use_denoising=True
    scene.view_settings.view_transform='AgX'
    scene.world=bpy.data.worlds.new('World');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(1,1,1,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.25
    for name,pos,power,size in [('Key',(0,-35,40),18000,30),('Fill',(-35,-15,15),10000,25),('Rim',(25,20,30),14000,20)]:
        bpy.ops.object.light_add(type='AREA',location=centre+Vector(pos));lamp=bpy.context.object
        lamp.name=name;lamp.data.energy=power;lamp.data.shape='DISK';lamp.data.size=size
        lamp.rotation_euler=(centre-lamp.location).to_track_quat('-Z','Y').to_euler()
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1e-6
    scene['inklet_source']=json.dumps(record['source'])
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


if __name__=='__main__':main()
