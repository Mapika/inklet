"""Orthographic Inklet drawings of released fly neuron skeletons and meshes.

All source coordinates are transformed together. Display simplification only
removes redundant points along chains; tips and branch points are retained.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import json

import inklet as i
from inklet.core import PathPrim, Subpath, Vec2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw
from scipy.interpolate import RBFInterpolator
from skimage.measure import find_contours, approximate_polygon
import trimesh


def paths(lines, color, *, width=.5, fill=False, opacity=1, name='anatomy'):
    subpaths = tuple(Subpath(tuple(Vec2(float(x), float(y)) for x,y in line), closed=fill) for line in lines if len(line)>1)
    if not subpaths:
        return i.Diagram(name=name)
    return i.Diagram(prim=PathPrim(subpaths, filled=fill, fill_rule='evenodd'), name=name,
                     kind='real-anatomy').styled(fill=color if fill else 'none',
                     stroke='none' if fill else color, stroke_width=width,
                     stroke_linecap='round', stroke_linejoin='round', opacity=opacity)


class Anatomy:
    def __init__(self, data):
        self.data = Path(data)
        self.manifest = json.loads((self.data/'manifest.json').read_text())
        lm = pd.read_csv(self.data/'JRCFIB2022M_plotting_landmarks.csv')
        source = lm[['mcns_x','mcns_y','mcns_z']].values/1000
        target = lm[['mcns_plot_x','mcns_plot_y','mcns_plot_z']].values/1000
        # The 3D polyharmonic/TPS radial basis is r (the sign convention is
        # absorbed by its coefficients); degree-1 terms preserve affine maps.
        self.transform = RBFInterpolator(source, target, kernel='linear', degree=1)
        self.landmark_error_um = float(np.abs(self.transform(source)-target).max())
        self._cached = self.data/'projected'; self._cached.mkdir(exist_ok=True)
        self.neurons = pd.read_feather(self.data/'selected-neurons.feather').set_index('bodyId')

    def warp(self, xyz):
        return np.concatenate([self.transform(xyz[k:k+3000]/1000) for k in range(0,len(xyz),3000)])

    @lru_cache(maxsize=1024)
    def skeleton(self, body):
        cache = self._cached/f'{body}.npz'
        if cache.exists():
            loaded = np.load(cache)
            return loaded['points'], loaded['ids'], loaded['parents']
        values = np.loadtxt(self.data/'skeletons'/f'{body}.swc', comments='#', ndmin=2)
        points = self.warp(values[:,2:5]*8)
        ids, parents = values[:,0].astype(int), values[:,6].astype(int)
        np.savez_compressed(cache, points=points, ids=ids, parents=parents)
        return points, ids, parents

    @lru_cache(maxsize=64)
    def mesh(self, name):
        cache = self._cached/f'{name}.npz'
        if cache.exists():
            loaded=np.load(cache); return loaded['vertices'], loaded['faces']
        if name in ('male-brain','male-vnc'):
            mesh=trimesh.load(self.data/(name+'.ply'), process=False)
            v,f=mesh.vertices,mesh.faces
        else:
            mesh=np.load(self.data/(name+'.npz'));v,f=mesh['vertices'],mesh['faces']
        v=self.warp(v)
        np.savez_compressed(cache,vertices=v,faces=f)
        return v,f

    @lru_cache(maxsize=128)
    def silhouette(self, name, view='front'):
        cache=self._cached/f'{name}-{view}-contours.json'
        if cache.exists():return [np.asarray(x) for x in json.loads(cache.read_text())]
        v,faces=self.mesh(name)
        v=self.project(v,view)
        lo,hi=v.min(0),v.max(0)
        scale=1100/max(hi-lo)
        q=(v-lo)*scale+3
        bitmap=Image.new('L',tuple(np.ceil((hi-lo)*scale+7).astype(int)),0)
        draw=ImageDraw.Draw(bitmap)
        for triangle in faces:
            draw.polygon([tuple(point) for point in q[triangle]],fill=255)
        contours=find_contours(np.asarray(bitmap),127.5)
        curves=[]
        for c in contours:
            if len(c)<5:continue
            c=approximate_polygon(c,.24)
            curves.append((c[:,::-1]-3)/scale+lo)
        cache.write_text(json.dumps([x.tolist() for x in curves],separators=(',',':')))
        return curves

    @staticmethod
    def project(points, view='front'):
        if view=='front':return points[:,:2]
        if view=='dorsal':return points[:,[0,2]]
        if view=='side':return points[:,[2,1]]
        raise ValueError(view)

    def ids(self, group, side=None):
        values=self.manifest['groups'][group]['ids']
        if side:
            values=[body for body in values if self.neurons.loc[body,'somaSide']==side]
        return values

    def frame(self, box, *, full=False, central=False, view='front', bounds=None, pad=0):
        if bounds is None:
            v=self.mesh('central-brain' if central else 'male-brain')[0]
            if full:v=np.concatenate([v,self.mesh('male-vnc')[0]])
            xy=self.project(v,view);lo,hi=xy.min(0),xy.max(0)
        else:lo,hi=np.asarray(bounds[0]),np.asarray(bounds[1])
        x,y,w,h=box
        scale=min((w-2*pad)/(hi[0]-lo[0]),(h-2*pad)/(hi[1]-lo[1]))
        offset=np.array([x+w/2,y+h/2])-(lo+hi)/2*scale
        return lambda points: points*scale+offset

    @lru_cache(maxsize=64)
    def display_mesh(self, name, target=4500):
        """Optional display reduction, cached separately from the true mesh."""
        from inklet.three import Mesh
        cache=self._cached/f'{name}-display-{target}.npz'
        if cache.exists():
            values=np.load(cache)
            return Mesh.from_arrays(values['vertices'],values['faces'],name=name)
        v,f=self.mesh(name)
        mesh=Mesh.from_arrays(v,f,name=name).simplified(target)
        np.savez_compressed(cache,vertices=np.array([(p.x,p.y,p.z) for p in mesh.vertices]),faces=np.array(mesh.faces))
        return mesh

    @staticmethod
    def camera(frame,view='front'):
        """Adapt the figure's existing physical frame to Inklet's shared View."""
        from inklet.three import View,Vec3
        origin=frame(np.array([0.,0.]));unit=frame(np.array([1.,0.]));scale=float(unit[0]-origin[0])
        if view=='front':eye,right,up,forward=Vec3(0,0,-1e6),Vec3(1,0,0),Vec3(0,-1,0),Vec3(0,0,1)
        elif view=='dorsal':eye,right,up,forward=Vec3(0,1e6,0),Vec3(1,0,0),Vec3(0,0,-1),Vec3(0,-1,0)
        else:eye,right,up,forward=Vec3(1e6,0,0),Vec3(0,0,1),Vec3(0,-1,0),Vec3(-1,0,0)
        return View(eye,right,up,forward,scale=scale,offset=i.Vec2(*origin))

    def surface(self,name,frame,*,view='front',color='#c7c3bf',opacity=.6,target=4500):
        mesh=self.display_mesh(name,target)
        node=i.model(mesh,view=self.camera(frame,view),style='solid',shading='smooth',
                     sort='depth',smooth=65,cull=True,ridges=False,hidden=False,
                     color=color,lift=.74,shade=.13,levels=16,opacity=opacity,name=name+'-structure')
        node.notes['source_surface']=dict(source=name,source_faces=len(self.mesh(name)[1]),display_faces=len(mesh.faces),method='Quadric-error display simplification, Inklet shaded vector facets; full geometry retained for alignment.')
        return [node]


    def shell(self, frame, *, full=False, central=False, view='front', color='#f3f2f2', outline='#cecbcb', width=.55):
        nodes=[]
        for name in ['central-brain' if central else 'male-brain']+(['male-vnc'] if full else []):
            curves=[frame(p) for p in self.silhouette(name,view)]
            nodes.append(paths(curves,color,fill=True,name=name+'-surface'))
            if outline:nodes.append(paths(curves,outline,width=width,name=name+'-outline'))
        return nodes

    def roi(self,name,frame,*,view='front',color='#edebeb',outline='#777777',width=.5):
        curves=[frame(p) for p in self.silhouette('roi-'+name,view)]
        return [paths(curves,color,fill=True,name=name), paths(curves,outline,width=width,name=name+'-outline')]

    def female(self,group,frame,*,view='front',color='#c057a1',opacity=.55):
        nodes=[]
        for body in self.manifest['female_groups'][group]:
            curves=[frame(p) for p in self.silhouette('female-'+str(body),view)]
            node=paths(curves,color,fill=True,opacity=opacity,name=f'FlyWire-{group}-{body}')
            node.notes['source_neuron']=dict(dataset='FlyWire v783, registered to MaleCNS',body_id=str(body))
            nodes.append(node)
        return nodes

    @lru_cache(maxsize=2048)
    def chains(self,body,view):
        xyz,ids,parents=self.skeleton(body)
        points=self.project(xyz,view)
        lookup={int(n):k for k,n in enumerate(ids)}
        children=np.zeros(len(ids),dtype=int)
        for parent in parents:
            if parent in lookup:children[lookup[parent]]+=1
        chains=[]
        for start in np.flatnonzero(children!=1):
            if parents[start] not in lookup:continue
            chain=[points[start]];current=start
            while parents[current] in lookup:
                current=lookup[parents[current]];chain.append(points[current])
                if children[current]!=1:break
            # 0.45 µm, considerably smaller than a reference pixel at full-brain scale.
            chains.append(approximate_polygon(np.asarray(chain),.45))
        return chains

    def neurons_draw(self, ids, frame, *, view='front', color='#709157', width=.45, opacity=.55, colors=None, depth_cue=0):
        nodes=[]
        for body in ids:
            curves=[frame(p) for p in self.chains(int(body),view)]
            c=colors.get(str(body),color) if colors else color
            if depth_cue:
                xyz,idx,parents=self.skeleton(int(body));lookup={int(v):k for k,v in enumerate(idx)}
                lines=[xyz[[k,lookup[int(parent)]]] for k,parent in enumerate(parents) if int(parent) in lookup]
                node=self.camera(frame,view).paths(lines,color=c,stroke_width=width,depth_cue=depth_cue,opacity=opacity,levels=6)
            else:
                node=paths(curves,c,width=width,opacity=opacity,name=f'MaleCNS-{int(body)}')
            node.notes['source_neuron']=dict(dataset='MaleCNS v1.0',body_id=int(body),cell_type=str(self.neurons.loc[body,'type']))
            nodes.append(node)
        return nodes

    def arbor_frame(self,box,ids,*,female_group=None,view='front',pad=3):
        vertices=[self.project(self.skeleton(int(body))[0],view) for body in ids]
        if female_group:
            vertices += [self.project(self.mesh('female-'+str(body))[0],view) for body in self.manifest['female_groups'][female_group]]
        xyz=np.concatenate(vertices)
        return self.frame(box,bounds=(xyz.min(0),xyz.max(0)),view=view,pad=pad)
