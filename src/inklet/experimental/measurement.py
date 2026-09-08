"""Calibrated 2D label measurements with explicit region identities."""
from dataclasses import dataclass
import hashlib
import json
import math

from .selection import KeyedTable


def _matrix(value, name):
    if not isinstance(value,(list,tuple)) or not value:
        raise ValueError(f'{name} needs a nonempty rectangular array')
    rows=[]
    for row in value:
        if not isinstance(row,(list,tuple)) or not row or (rows and len(row)!=len(rows[0])):
            raise ValueError(f'{name} needs a nonempty rectangular array')
        rows.append(tuple(row))
    return tuple(rows)


@dataclass(frozen=True)
class LabelImage:
    """Snapshot an intensity grid, integer labels and physical pixel spacing.

    Label 0 is background. Every observed positive label must map to one unique
    stable region ID, and every mapped label must occur. Missing intensities
    (None) retain labeled area but do not enter intensity statistics.
    """
    intensity: tuple
    labels: tuple
    regions: tuple[tuple[str,int],...]
    spacing_yx: tuple[float,float]
    unit: str

    def __post_init__(self):
        intensity=_matrix(self.intensity,'intensity');labels=_matrix(self.labels,'labels')
        if (len(intensity),len(intensity[0]))!=(len(labels),len(labels[0])):
            raise ValueError('intensity and labels must have the same shape')
        if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v)) for row in intensity for v in row):
            raise ValueError('intensities must be finite numbers or None')
        if any(type(v) is not int or not 0<=v<=2**53-1 for row in labels for v in row):
            raise ValueError('labels must be nonnegative safe integers')
        if not isinstance(self.regions,(list,tuple)): raise ValueError('regions need (ID, label) pairs')
        regions=[];ids=set();numbers=set()
        for pair in self.regions:
            if not isinstance(pair,(list,tuple)) or len(pair)!=2: raise ValueError('regions need (ID, label) pairs')
            key,label=pair
            if not isinstance(key,str) or not key or key in ids: raise ValueError('region IDs must be unique nonempty strings')
            if type(label) is not int or not 1<=label<=2**53-1 or label in numbers:
                raise ValueError('region labels must be unique positive safe integers')
            ids.add(key);numbers.add(label);regions.append((key,label))
        present={v for row in labels for v in row if v}
        if present!=numbers:
            raise ValueError(f'label correspondence mismatch: unmapped {sorted(present-numbers)}, absent {sorted(numbers-present)}')
        if (not isinstance(self.spacing_yx,(list,tuple)) or len(self.spacing_yx)!=2 or
                any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in self.spacing_yx)):
            raise ValueError('spacing_yx needs two finite positive physical spacings')
        if self.unit not in ('m','mm','um','nm'): raise ValueError('image unit must be m, mm, um or nm')
        spacing=tuple(self.spacing_yx);area=math.prod(spacing)
        dimensions=(len(labels[0])*spacing[1],len(labels)*spacing[0])
        if any(not math.isfinite(v) or v<=0 for v in (*dimensions,area,area*len(labels)*len(labels[0]))):
            raise ValueError('physical image extent or pixel area is not representable')
        object.__setattr__(self,'intensity',intensity);object.__setattr__(self,'labels',labels)
        object.__setattr__(self,'regions',tuple(regions));object.__setattr__(self,'spacing_yx',spacing)

    @classmethod
    def from_dict(cls,source):
        if not isinstance(source,dict): raise ValueError('image source must be an object')
        regions=source.get('regions')
        if not isinstance(regions,list) or any(not isinstance(r,dict) for r in regions):
            raise ValueError('regions must be an array of ID/label objects')
        return cls(source.get('intensity'),source.get('labels'),
                   [(r.get('id'),r.get('label')) for r in regions],source.get('spacing_yx'),source.get('unit'))

    @property
    def shape(self): return len(self.labels),len(self.labels[0])

    @property
    def extent(self): return self.shape[1]*self.spacing_yx[1],self.shape[0]*self.spacing_yx[0]

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(dict(intensity=self.intensity,labels=self.labels,regions=self.regions,
            spacing_yx=self.spacing_yx,unit=self.unit),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

    def table(self,name='image-regions'):
        """Area counts labeled pixels; mean/range use valid source intensities."""
        columns={key:[] for key in ('id','label','pixels','valid_pixels','missing_pixels','area','mean','minimum','maximum')}
        counts={label:0 for _,label in self.regions};samples={label:[] for _,label in self.regions}
        for labels,values in zip(self.labels,self.intensity):
            for label,value in zip(labels,values):
                if not label: continue
                counts[label]+=1
                if value is not None:samples[label].append(value)
        for key,label in self.regions:
            values=samples[label];n=len(values)
            # Sum normalized terms to avoid overflowing an otherwise finite mean.
            scale=max(map(abs,values)) if n else 0
            mean=(scale*math.fsum((v/scale)/n for v in values) if scale else 0.0) if n else None
            row=(key,label,counts[label],n,counts[label]-n,counts[label]*math.prod(self.spacing_yx),
                 mean,min(values) if n else None,max(values) if n else None)
            for column,value in zip(columns,row):columns[column].append(value)
        return KeyedTable(name,columns)

    def report(self):
        return dict(schema='inklet.label-image/0.1',source_digest=self.digest,shape_yx=self.shape,
                    spacing_yx=self.spacing_yx,unit=self.unit,extent_xy=self.extent,
                    regions=self.regions,background_pixels=sum(v==0 for row in self.labels for v in row),
                    area_method='labeled source pixel count × row spacing × column spacing',
                    intensity_method='arithmetic mean and observed minimum/maximum of nonmissing labeled source pixels',
                    missing='exclude None from intensity summaries; retain labeled area',
                    coordinates='pixel edges start at (0,0); X rightward, Y downward')
