"""Registered microscopy channels with explicit display windows and coverage."""
from dataclasses import dataclass
import io
import math

import inklet as i
from inklet.core import ImagePrim
from inklet.themes.color import parse_color, to_hex
from .sections import SampledSection, _snapshot
from .slabs import SlabProjection
from .volume import _numpy, _positive


def _geometry(sampled):
    if isinstance(sampled,SampledSection) and sampled.kind=='intensity':
        return ('section',sampled.plane)
    if isinstance(sampled,SlabProjection):
        return ('slab',sampled.slab)
    raise ValueError('Channels require an intensity SampledSection or SlabProjection, not label IDs')


@dataclass(frozen=True)
class Channel:
    """One sampled intensity signal and its explicit display mapping.

    Colors are display RGB, independent of acquisition wavelengths. Weight is
    in (0,1]; omit a channel to disable it. Original sampled values stay intact.
    """
    name: str
    sampled: SampledSection | SlabProjection
    color: str
    window: tuple[float,float]
    weight: float = 1.

    def __post_init__(self):
        if not isinstance(self.name,str) or not self.name.strip():
            raise ValueError('Channel name must be nonempty')
        _geometry(self.sampled)
        window=tuple(float(v) for v in self.window)
        if len(window)!=2 or not all(math.isfinite(v) for v in window):
            raise ValueError('Channel window must contain two finite limits')
        _positive(window[1]-window[0],'channel window range')
        weight=_positive(self.weight,'channel weight')
        if weight>1:raise ValueError('Channel weight must be at most 1')
        if not isinstance(self.color,str):raise ValueError('Channel color must be a CSS color string')
        object.__setattr__(self,'color',to_hex(parse_color(self.color)))
        object.__setattr__(self,'window',window)
        object.__setattr__(self,'weight',weight)

    @property
    def plane(self):
        return self.sampled.plane if isinstance(self.sampled,SampledSection) else self.sampled.slab.plane

    def report(self):
        np=_numpy();values=self.sampled.data[self.sampled.valid]
        return dict(name=self.name,color=self.color,window=list(self.window),weight=self.weight,
                    sampled=self.sampled.report(),valid_pixels=int(values.size),
                    below_window=int(np.count_nonzero(values<self.window[0])),
                    above_window=int(np.count_nonzero(values>self.window[1])))


@dataclass(frozen=True, eq=False)
class Composite:
    """Additive display RGB from channels sharing exactly the same sampling geometry.

    Coverage must be explicitly chosen: intersection requires every channel at
    a pixel; union permits missing channels to contribute no display signal.
    """
    channels: tuple[Channel,...]
    coverage: str

    def __post_init__(self):
        channels=tuple(self.channels)
        if not channels or any(not isinstance(c,Channel) for c in channels):
            raise ValueError('Composite requires at least one Channel')
        if len({c.name for c in channels})!=len(channels):
            raise ValueError('Channel names must be unique within a composite')
        if self.coverage not in ('intersection','union'):
            raise ValueError('Composite coverage must be intersection or union')
        geometry=_geometry(channels[0].sampled)
        if any(_geometry(c.sampled)!=geometry for c in channels[1:]):
            raise ValueError('Channels must share the same plane and section/slab sampling geometry')
        object.__setattr__(self,'channels',channels)

    @property
    def plane(self):
        return self.channels[0].plane

    def _blend(self):
        np=_numpy()
        rgb=np.zeros((*self.plane.shape_yx,3),dtype=float)
        count=np.zeros(self.plane.shape_yx,dtype=np.int64)
        # Stable accumulation order makes display bytes independent of legend order.
        for channel in sorted(self.channels,key=lambda c:c.name):
            values=channel.sampled.data
            valid=channel.sampled.valid
            low,high=channel.window
            normalized=(np.clip(values.astype(float),low,high)-low)/(high-low)
            normalized=np.where(valid,normalized,0)*channel.weight
            rgb+=normalized[:,:,None]*(np.array(parse_color(channel.color))/255)
            count+=valid
        valid=(count==len(self.channels)) if self.coverage=='intersection' else (count>0)
        clipped=int(np.count_nonzero(np.any(rgb>1,axis=-1)&valid))
        rgba=np.empty((*self.plane.shape_yx,4),dtype=np.uint8)
        rgba[:,:,:3]=np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)
        rgba[:,:,3]=valid*255
        rgba[~valid]=0
        return rgba,valid,count,clipped

    @property
    def rgba(self):
        return _snapshot(self._blend()[0])

    @property
    def valid(self):
        return _snapshot(self._blend()[1])

    @property
    def channel_counts(self):
        """Available channels per pixel, not depth samples or a confidence score."""
        return _snapshot(self._blend()[2])

    def report(self):
        _,valid,count,clipped=self._blend()
        return self._report(valid,count,clipped)

    def _report(self,valid,count,clipped):
        np=_numpy()
        return dict(schema='inklet.channel-composite/0.1',plane=self.plane.report(),coverage=self.coverage,
                    channels=[c.report() for c in self.channels],valid_pixels=int(valid.sum()),
                    total_pixels=int(valid.size),complete_pixels=int(np.count_nonzero(count==len(self.channels))),
                    partial_pixels=int(np.count_nonzero((count>0)&(count<len(self.channels)))),
                    rgb_clipped_pixels=clipped,
                    blending='additive display RGB after linear channel windowing; clip to [0,1]; no gamma transform')

    def diagram(self, *, width):
        from PIL import Image
        width=_positive(width,'width')
        rgba,valid,count,clipped=self._blend()
        buffer=io.BytesIO();Image.fromarray(rgba).save(buffer,format='PNG')
        return i.Diagram(prim=ImagePrim(source=' / '.join(c.name for c in self.channels),width=width,
            height=width*self.plane.extent[1]/self.plane.extent[0],data=buffer.getvalue(),smooth=False),
            kind='channel-composite',notes={'channel_composite':self._report(valid,count,clipped)|dict(width_mm=width)})

    def legend(self, *, size=i.pt(8)):
        """Vector color keys recording channel names, windows and display weights."""
        rows=[]
        for c in self.channels:
            swatch=i.box(width=3,height=3,pad=0,radius=0,fill=c.color,stroke='#172f32',stroke_width=.25)
            label=i.text(f'{c.name} [{c.window[0]:g}, {c.window[1]:g}] × {c.weight:g}',size=size)
            rows.append(i.hstack([swatch,label],gap=2))
        return i.vstack(rows,gap=2)
