"""Shared source-coordinate sections and exact visibility of vector overlays."""
from __future__ import annotations
import math
from .mesh import Mesh,MeshError
from .overlays import _xyz
from .hlr import Occluders,_depth_at


def plane(normal,offset):
    normal=_xyz(normal);offset=float(offset)
    if normal.dot(normal)==0 or not math.isfinite(offset):raise MeshError('section needs a nonzero normal and finite offset')
    return normal,offset


def clip_mesh(mesh,normal,offset):
    """Keep n·p >= offset. Cut boundaries are open, never fabricated caps."""
    normal,offset=plane(normal,offset);vertices=[];faces=[];groups=[];lookup={}
    def vertex(p):
        key=(p.x,p.y,p.z)
        if key not in lookup:lookup[key]=len(vertices);vertices.append(p)
        return lookup[key]
    for index,face in enumerate(mesh.faces):
        points=[mesh.vertices[k] for k in face];clipped=[]
        for a,b in zip(points,points[1:]+points[:1]):
            da,db=normal.dot(a)-offset,normal.dot(b)-offset
            if da>=0:clipped.append(a)
            if (da<0)!=(db<0):clipped.append(a+(b-a)*(da/(da-db)))
        if len(clipped)<3:continue
        ids=[vertex(p) for p in clipped]
        for k in range(1,len(ids)-1):
            triangle=(ids[0],ids[k],ids[k+1])
            if len(set(triangle))<3:continue
            a,b,c=(vertices[v] for v in triangle)
            if (b-a).cross(c-a).dot((b-a).cross(c-a))<1e-24:continue
            faces.append(triangle)
            if mesh.groups:groups.append(mesh.groups[index])
    return Mesh(tuple(vertices),tuple(faces),tuple(groups),mesh.name)


def clip_paths(lines,normal,offset):
    normal,offset=plane(normal,offset);result=[]
    for line in lines:
        for a,b in zip(line,line[1:]):
            da,db=normal.dot(a)-offset,normal.dot(b)-offset
            if da<0 and db<0:continue
            if da<0:a=a+(b-a)*(da/(da-db))
            elif db<0:b=a+(b-a)*(da/(da-db))
            if a!=b:result.append((a,b))
    return tuple(result)


class SurfaceVisibility:
    """Triangle-indexed visibility, also splitting surface-piercing segments."""
    def __init__(self,mesh,view):
        self.mesh=mesh;self.view=view
        points,depths=view.project_all(mesh.vertices)
        if depths and min(depths)<view.near:raise MeshError('occluding surface crosses the camera near plane')
        self.index=Occluders(mesh,view,points,depths,list(range(len(mesh.faces))))
        self.margin=max((max(depths)-min(depths))*1e-7,1e-10) if depths else 1e-10
    def visible_point(self,point):
        hit=self.view.project(point)
        if hit.depth<self.view.near:raise MeshError('overlay crosses the camera near plane')
        return not self.index.hides(hit.point,hit.depth,self.index.near(hit.point,hit.point),(),self.margin)
    def paths(self,lines):
        result=[]
        for line in lines:
            for a,b in zip(line,line[1:]):
                ha,hb=self.view.project(a),self.view.project(b);p,q=ha.point,hb.point;delta=q-p
                if min(ha.depth,hb.depth)<self.view.near:raise MeshError('overlay crosses the camera near plane')
                if delta.length<1e-12:continue
                candidates=self.index.near(p,q);cuts=[0.,1.,*self.index.crossings(p,q,candidates,())]
                for index in candidates:
                    face=self.index.tri[index][0];u,v,w=(self.mesh.vertices[k] for k in self.mesh.faces[face]);n=(v-u).cross(w-u)
                    denom=n.dot(b-a)
                    if abs(denom)>1e-15:
                        t=n.dot(u-a)/denom
                        if 0<t<1:
                            hit=self.view.project(a+(b-a)*t).point
                            s=((hit.x-p.x)*delta.x+(hit.y-p.y)*delta.y)/(delta.length**2)
                            if 0<s<1:cuts.append(s)
                cuts=sorted(set(cuts))
                for lo,hi in zip(cuts,cuts[1:]):
                    if hi-lo<1e-9:continue
                    mid=(lo+hi)/2
                    if self.index.hides(p+delta*mid,_depth_at(ha.depth,hb.depth,mid,self.view.perspective),candidates,(),self.margin):continue
                    def source(s):return s*ha.depth/((1-s)*hb.depth+s*ha.depth) if self.view.perspective else s
                    result.append((a+(b-a)*source(lo),a+(b-a)*source(hi)))
        return tuple(result)
