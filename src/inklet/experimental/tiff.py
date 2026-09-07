"""Local, single-file microscopy TIFF import with explicit calibration."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from .volume import Volume, _numpy


@dataclass(frozen=True)
class TiffImage:
    """Named immutable scalar volumes plus import provenance."""
    names: tuple[str,...]
    volumes: tuple[Volume,...]
    _provenance: str

    @property
    def channels(self):
        return dict(zip(self.names,self.volumes))

    def report(self):
        return json.loads(self._provenance)


def read_tiff(path, *, spacing_zyx, unit, source_id, channel_names=None,
              origin_xyz=(0.,0.,0.), series=0, time_index=None, axes=None):
    """Read a calibrated ZYX volume per channel from a local TIFF series.

    Axes come from tifffile unless explicitly supplied for ambiguous stacks.
    Only T,C,Z,Y,X are supported; RGB samples and external-file OME data are
    rejected. Physical spacing/origin are caller declarations, never guessed
    from TIFF resolution tags or silently substituted from OME metadata.
    """
    np=_numpy()
    try:
        import tifffile
    except ImportError as error:
        raise ImportError('Microscopy TIFF import requires inklet[volume]') from error
    if type(series) is not int or series<0:raise ValueError('series must be a nonnegative integer')
    if time_index is not None and (type(time_index) is not int or time_index<0):
        raise ValueError('time_index must be a nonnegative integer')
    if isinstance(channel_names,str):raise ValueError('channel_names must be a sequence of names')
    path=Path(path)
    with path.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest();stream.seek(0)
        with tifffile.TiffFile(stream, _multifile=False) as source:
            if source.ome_metadata:
                root=ET.fromstring(source.ome_metadata)
                for node in root.iter():
                    if node.tag.rsplit('}',1)[-1]=='UUID':
                        filename=node.get('FileName')
                        if (filename and filename!=path.name) or (not filename and node.text and node.text!=root.get('UUID')):
                            raise ValueError('External-file OME-TIFF is not supported')
            if series>=len(source.series):raise ValueError('TIFF series index is out of range')
            selected=source.series[series]
            if any(page is None or not all(page.dataoffsets) or not all(page.databytecounts) for page in selected.pages):
                raise ValueError('TIFF series contains missing image data')
            if any(page.keyframe.photometric==2 for page in selected.pages if page is not None):
                raise ValueError('RGB TIFF samples are not microscopy channels')
            native_axes=selected.axes;shape=tuple(selected.shape)
            declared=native_axes if axes is None else axes
            if not isinstance(declared,str) or len(declared)!=len(shape) or len(set(declared))!=len(declared):
                raise ValueError('TIFF axes must uniquely name each array dimension')
            if set(declared)-set('TCZYX') or not set('YX').issubset(declared):
                raise ValueError('TIFF axes must use T,C,Z,Y,X; supply axes explicitly for ambiguous stacks')
            if 'T' in declared:
                if time_index is None:raise ValueError('A TIFF with a T axis requires an explicit time_index')
                if time_index>=shape[declared.index('T')]:raise ValueError('time_index is out of range')
            elif time_index is not None:
                raise ValueError('time_index supplied for a TIFF without a T axis')
            array=selected.asarray()
    used_axes=declared
    if 'T' in used_axes:
        array=np.take(array,time_index,axis=used_axes.index('T'));used_axes=used_axes.replace('T','')
    for axis in 'CZ':
        if axis not in used_axes:
            array=np.expand_dims(array,0);used_axes=axis+used_axes
    array=np.transpose(array,tuple(used_axes.index(axis) for axis in 'CZYX'))
    names=tuple(channel_names) if channel_names is not None else tuple(f'channel-{n}' for n in range(array.shape[0]))
    if len(names)!=array.shape[0] or any(not isinstance(n,str) or not n.strip() for n in names) or len(set(names))!=len(names):
        raise ValueError('channel_names must uniquely name every channel')
    if not isinstance(source_id,str) or not source_id.strip():raise ValueError('source_id must identify the TIFF source')
    # Canonicalize iterables once so all channels receive the same calibration.
    spacing_zyx=tuple(spacing_zyx);origin_xyz=tuple(origin_xyz)
    volumes=tuple(Volume(data,spacing_zyx,unit,origin_xyz,f'{source_id} / series {series} / time {time_index} / channel {index} / {name}')
                  for index,(name,data) in enumerate(zip(names,array)))
    report=dict(schema='inklet.microscopy-tiff/0.1',source_id=source_id,file=path.name,sha256=digest,
        reader='tifffile',reader_version=tifffile.__version__,series=series,time_index=time_index,
        native_axes=native_axes,declared_axes=declared,axes_override=axes is not None,source_shape=list(shape),
        calibration='explicit caller-supplied spacing and origin; no metadata calibration inferred',
        channels=[dict(index=n,name=name,volume=v.report()) for n,(name,v) in enumerate(zip(names,volumes))])
    return TiffImage(names,volumes,json.dumps(report,allow_nan=False))
