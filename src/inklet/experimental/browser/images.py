"""Calibrated reference images with exact labeled-pixel selection targets."""
import base64
from dataclasses import dataclass
import math
import re
import struct
import zlib

from ..measurement import LabelImage
from .drawings import DrawingItem,DrawingView


_PALETTE=('#81aaa2','#d8a36b','#9c99be','#88b47f','#c38d9b','#7fa8c4','#b3ae73','#bb957c')


def _png(width,height,pixels):
    """Deterministic RGB8 PNG, using standard-library lossless compression."""
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    raw=b''.join(b'\0'+bytes(pixels[y*width*3:(y+1)*width*3]) for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


@dataclass(frozen=True)
class LabelImageView:
    """Fixed reference pixels; row filtering affects outlines and picking only.

    Labels are measured in Python, with one row per region. Row runs provide
    exact pixel membership without bounding-box selection across holes. Source
    imagery is embedded as a lossless PNG; boundaries and scale bars are vector.
    """
    name: str
    image: LabelImage
    window: tuple[float,float]
    scale_bar: float
    mode: str = 'intensity'
    palette: tuple[str,...] = _PALETTE

    def __post_init__(self):
        if not isinstance(self.name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',self.name):
            raise ValueError('view name needs a stable document cell identifier')
        if not isinstance(self.image,LabelImage): raise ValueError('image must be a LabelImage')
        if math.prod(self.image.shape)>65536: raise ValueError('browser label images support at most 65,536 source pixels')
        if (not isinstance(self.window,(tuple,list)) or len(self.window)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) for v in self.window) or
                self.window[0]>=self.window[1] or not math.isfinite(self.window[1]-self.window[0])):
            raise ValueError('image window needs increasing finite endpoints with a finite span')
        if type(self.scale_bar) not in (int,float) or not math.isfinite(self.scale_bar) or not 0<self.scale_bar<=self.image.extent[0]:
            raise ValueError('scale_bar must be positive and no longer than the image width')
        if self.mode not in ('intensity','labels'): raise ValueError('image mode must be intensity or labels')
        palette=tuple(self.palette)
        if not palette or any(not isinstance(c,str) or not re.fullmatch('#[0-9a-fA-F]{6}',c) for c in palette):
            raise ValueError('palette needs six-digit hex colors')
        object.__setattr__(self,'palette',palette);object.__setattr__(self,'window',tuple(self.window))

    def validate_table(self,table):
        expected=self.image.table(table.name)
        if set(table.row_ids)!=set(expected.row_ids): raise ValueError('image/table region ID mismatch')
        required=expected.columns
        if set(required)-set(table.columns): raise ValueError('image table lacks derived measurement columns')
        indices={key:n for n,key in enumerate(table.row_ids)}
        for n,key in enumerate(expected.row_ids):
            for column in required:
                value=table.columns[column][indices[key]];correct=required[column][n]
                if type(value) is not type(correct) or value!=correct:
                    raise ValueError(f'image/table measurement mismatch for {key}, {column}; rebuild the table from this image')

    def layer(self,table,bounds):
        self.validate_table(table)
        image=self.image;ny,nx=image.shape;sx,sy=image.spacing_yx[1],image.spacing_yx[0]
        scale=min((bounds[2]-4)/image.extent[0],(bounds[3]-12)/image.extent[1])
        if not math.isfinite(scale) or scale<=0: raise ValueError('image does not fit its measured panel')
        w,h=image.extent[0]*scale,image.extent[1]*scale
        x0=bounds[0]+(bounds[2]-w)/2;y0=bounds[1]+(bounds[3]-12-h)/2+1
        def point(x,y):return [round(x0+x*sx*scale,6),round(y0+y*sy*scale,6)]
        pixels=[];lo,hi=self.window
        for labels,values in zip(image.labels,image.intensity):
            for label,value in zip(labels,values):
                if self.mode=='labels':
                    color=self.palette[(label-1)%len(self.palette)] if label else '#f1f4f2'
                    rgb=[int(color[k:k+2],16) for k in (1,3,5)]
                elif value is None:rgb=[225,214,225]
                else:
                    gray=round(255*min(1,max(0,(value-lo)/(hi-lo))));rgb=[gray]*3
                pixels.extend(rgb)
        href='data:image/png;base64,'+base64.b64encode(_png(nx,ny,pixels)).decode()
        marks=[dict(kind='image',ids=[],reference=True,geometry=[round(x0,6),round(y0,6),round(w,6),round(h,6)],
                    bounds=[x0,y0,x0+w,y0+h],href=href,smooth=False,preserve_aspect=False)]
        ids={label:key for key,label in image.regions}
        for row,labels in enumerate(image.labels):
            column=0
            while column<nx:
                label=labels[column];end=column+1
                while end<nx and labels[end]==label:end+=1
                if label:
                    a,b=point(column,row),point(end,row+1)
                    marks.append(dict(kind='rect',ids=[ids[label]],geometry=[*a,round(b[0]-a[0],6),round(b[1]-a[1],6)],
                                      opacity=0,highlight=False,description=f'{ids[label]}; label {label}'))
                column=end
            for column,label in enumerate(labels):
                if not label:continue
                edges=[(row-1,column,(column,row,column+1,row)),(row+1,column,(column,row+1,column+1,row+1)),
                       (row,column-1,(column,row,column,row+1)),(row,column+1,(column+1,row,column+1,row+1))]
                for rr,cc,(ax,ay,bx,by) in edges:
                    if 0<=rr<ny and 0<=cc<nx and image.labels[rr][cc]==label:continue
                    marks.append(dict(kind='line',ids=[ids[label],ids[label]],geometry=[*point(ax,ay),*point(bx,by)],
                                      width=.12,selected_width=.4,color='#ffffff',pickable=False))
            if len(marks)>20000: raise ValueError('browser label image exceeds 20,000 selection/outline marks; simplify labels or crop the image')
        def scale_drawing(t,pw,ph):
            import inklet as i
            from ...core import group
            length=self.scale_bar*scale;left=(pw-w)/2;top=y0-bounds[1]+h+3
            bar=i.box(width=length,height=.4,pad=0,radius=0,fill='#172f32',stroke='none').translated(left+length/2,top)
            unit='µm' if image.unit=='um' else image.unit
            text=i.text(f'{self.scale_bar:g} {unit}',size=i.pt(8),markup=False)
            text=text.translated(left-text.bbox.x0,top+2-text.bbox.y0)
            return [DrawingItem((),group([bar,text]))]
        marks.extend(DrawingView(self.name,scale_drawing).layer(table,bounds)['marks'])
        return dict(name=self.name,x='area',y='mean',clip=bounds,marks=marks,color='#34786b',
                    image=image.report()|dict(mode=self.mode,window=self.window,scale_bar=self.scale_bar,
                        image_box=[x0,y0,w,h],pixel_size_mm=[sx*scale,sy*scale],
                        filtering='fixed source image; boundaries and picking follow visible region IDs',
                        picking='labeled source-pixel row runs; background and holes are unpickable'))
