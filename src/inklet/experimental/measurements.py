"""Per-label intensity statistics on calibrated native or sampled grids."""
from collections.abc import Mapping
from dataclasses import dataclass
import csv
import io
import json
import math

from .volume import Volume, _numpy
from .sections import SampledSection
from .regions import BoxRegion


@dataclass(frozen=True)
class LabelMeasurements:
    """A reproducible long-form table; report and row access return fresh copies."""
    _payload: str

    def report(self):
        return json.loads(self._payload)

    @property
    def rows(self):
        return tuple(self.report()['rows'])

    def to_json(self):
        return json.dumps(self.report(),indent=2,allow_nan=False)+'\n'

    def to_csv(self):
        """Long-form CSV; retain label_id as text when importing large IDs."""
        output=io.StringIO(newline='')
        fields=['label_id','channel','selected_count','count','excluded_count','coverage_fraction',
                'mean','std','minimum','maximum','sum','measure','measure_unit','integral']
        writer=csv.DictWriter(output,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(self.rows)
        return output.getvalue()


def measure_labels(labels, channels, *, label_ids=None, region=None, coverage='intersection'):
    """Measure source intensities without display windows, weights or RGB conversion.

    Native volumes must share shape, spacing, origin and unit. Sampled sections
    must share one Plane. Slab projections are deliberately not label sections.
    Standard deviation is population spread (ddof=0), not uncertainty of a mean.
    """
    np=_numpy()
    if not isinstance(channels,Mapping) or not channels:
        raise ValueError('channels must be a nonempty name-to-intensity mapping')
    if any(not isinstance(name,str) or not name.strip() for name in channels):
        raise ValueError('Channel names must be nonempty strings')
    if coverage not in ('intersection','per-channel'):
        raise ValueError('Measurement coverage must be intersection or per-channel')
    if isinstance(labels,Volume):
        def geometry(v):return (v.data.shape,v.spacing_zyx,v.origin_xyz,v.unit)
        if labels.data.dtype.kind not in 'bui':raise ValueError('Labels must be integer values')
        if any(not isinstance(v,Volume) or geometry(v)!=geometry(labels) for v in channels.values()):
            raise ValueError('Native channel and label grids must match exactly')
        selected=np.ones(labels.data.shape,dtype=bool)
        valid={name:None for name in channels}
        element_measure=math.prod(labels.spacing_zyx);unit=labels.unit;dimension=3
        if region is not None:
            _region(region,unit)
            for dim in range(3):
                coordinate=labels.origin_xyz[2-dim]+np.arange(labels.data.shape[dim])*labels.spacing_zyx[dim]
                inside=(coordinate>=region.lower_xyz[2-dim])&(coordinate<region.upper_xyz[2-dim])
                shape=[1,1,1];shape[dim]=len(coordinate)
                selected &= inside.reshape(shape)
        mode='native voxel centres'
    elif isinstance(labels,SampledSection) and labels.kind=='labels':
        if any(not isinstance(v,SampledSection) or v.kind!='intensity' or v.plane!=labels.plane for v in channels.values()):
            raise ValueError('Intensity and label sections must share the same Plane')
        selected=labels.valid.copy()
        valid={name:v.valid for name,v in channels.items()}
        element_measure=math.prod(labels.plane.spacing_yx);unit=labels.plane.unit;dimension=2
        if region is not None:
            _region(region,unit);selected &= region.mask(labels.plane)
        mode='sampled section pixel centres'
    else:
        raise ValueError('Labels must be an integer Volume or label SampledSection')
    if labels.data.dtype.kind=='i' and (labels.data[selected]<0).any():
        raise ValueError('Selected label IDs must be nonnegative')
    if not math.isfinite(int(selected.sum())*element_measure):
        raise ValueError('Selected physical measure exceeds finite floating-point range')
    # Compact inverse indices avoid allocation indexed by possibly enormous IDs.
    ids,inverse=np.unique(labels.data[selected],return_inverse=True)
    lookup={int(label):index for index,label in enumerate(ids)}
    if label_ids is None:
        requested=[int(label) for label in ids if label!=0]
    else:
        requested=list(label_ids)
        if any(type(label) is not int or label<0 for label in requested) or len(set(requested))!=len(requested):
            raise ValueError('label_ids must be unique nonnegative Python integers')
    selected_counts=np.bincount(inverse,minlength=len(ids))
    common=np.ones(inverse.shape,dtype=bool)
    if coverage=='intersection':
        for available in valid.values():
            if available is not None:common &= available[selected]
    statistics={}
    for name,channel in channels.items():
        available=common if coverage=='intersection' or valid[name] is None else valid[name][selected]
        group=inverse[available]
        values=channel.data[selected][available].astype(float)
        counts=np.bincount(group,minlength=len(ids))
        sums=np.bincount(group,weights=values,minlength=len(ids))
        means=np.divide(sums,counts,out=np.zeros(len(ids)),where=counts>0)
        with np.errstate(over='ignore',invalid='ignore'):
            variance=np.bincount(group,weights=(values-means[group])**2,minlength=len(ids))
        std=np.sqrt(np.divide(variance,counts,out=np.zeros(len(ids)),where=counts>0))
        low=np.full(len(ids),np.inf);high=np.full(len(ids),-np.inf)
        np.minimum.at(low,group,values);np.maximum.at(high,group,values)
        with np.errstate(over='ignore',invalid='ignore'):
            integrals=sums*element_measure
        if any(not np.isfinite(a[counts>0]).all() for a in (sums,means,std,low,high,integrals)):
            raise ValueError('Intensity statistics exceed finite floating-point range')
        statistics[name]=(counts,sums,means,std,low,high,integrals)
    rows=[]
    for label in requested:
        index=lookup.get(label)
        total=int(selected_counts[index]) if index is not None else 0
        for name,stats in statistics.items():
            counts,sums,means,std,low,high,integrals=stats
            count=int(counts[index]) if index is not None else 0
            rows.append(dict(label=label,label_id=str(label),channel=name,selected_count=total,count=count,
                excluded_count=total-count,coverage_fraction=count/total if total else None,
                mean=float(means[index]) if count else None,std=float(std[index]) if count else None,
                minimum=float(low[index]) if count else None,maximum=float(high[index]) if count else None,
                sum=float(sums[index]) if count else 0.,measure=count*element_measure,measure_unit=unit+f'^{dimension}',
                integral=float(integrals[index]) if count else 0.))
    report=dict(schema='inklet.label-intensities/0.1',labels=labels.report(),
        channels={name:c.report() for name,c in channels.items()},coverage=coverage,
        selection=region.report() if region else None,rows=rows,geometry=mode,
        element_measure=element_measure,measure_unit=unit+f'^{dimension}',
        intensity_unit='source intensity; no inferred intensity calibration',
        statistics='float64; population standard deviation (ddof=0); sum of measured values; integral = sum * element measure',
        missing='unavailable samples excluded; count zero has null mean/spread/extrema and zero sum/integral',
        interpretation='sample statistics, not biological replication, uncertainty or colocalization')
    return LabelMeasurements(json.dumps(report,allow_nan=False))


def _region(region,unit):
    if not isinstance(region,BoxRegion) or region.unit!=unit:
        raise ValueError('Region must be a BoxRegion with matching physical units')
