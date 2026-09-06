"""Numeric pass contracts without requiring Blender or an EXR library."""
import struct
from io import BytesIO

import pytest
import inklet as i


def make(name, values, pixels=(2,2)):
    channels=3 if name=='normal' else 1
    return i.ScenePass(name,pixels,channels,40,20,struct.pack('<'+'f'*len(values),*values))


def test_pass_values_validate_coordinates_and_dimensions():
    depth=make('depth',[1,2,3,4])
    assert depth.value(1,0)==2 and depth.value(0,1)==3
    with pytest.raises(IndexError):depth.value(-1,0)
    with pytest.raises(TypeError):depth.value(.5,0)
    with pytest.raises(ValueError):make('depth',[1])
    with pytest.raises(ValueError):make('unknown',[1,2,3,4])


def test_pass_visualizations_and_masks_keep_data(tmp_path):
    pytest.importorskip('numpy')
    Image=pytest.importorskip('PIL.Image')
    depth=make('depth',[2,4,1e10,float('inf')])
    art=depth.to_diagram(value_range=(2,4))
    picture=Image.open(BytesIO(art.prim.data))
    assert picture.getpixel((0,0))==(255,255,255,255)
    assert picture.getpixel((1,0))==(0,0,0,255)
    assert picture.getpixel((0,1))[3]==0 and picture.getpixel((1,1))[3]==0
    assert depth.value(1,0)==4
    assert art.notes['raster_layer']['value_range']==[2,4]
    with pytest.raises(ValueError):depth.to_diagram(value_range=(4,2))
    normal=make('normal',[-1,0,1,0,0,0],pixels=(2,1))
    picture=Image.open(BytesIO(normal.to_diagram().prim.data))
    assert picture.getpixel((0,0))==(0,128,255,255)
    assert picture.getpixel((1,0))[3]==0
    ids=make('object_id',[0,1,2,3])
    picture=Image.open(BytesIO(ids.object_mask([1,3]).prim.data))
    assert picture.getchannel('A').tobytes()==bytes([0,255,0,255])
    with pytest.raises(ValueError):ids.object_mask([0])
    with pytest.raises(ValueError):normal.to_diagram(value_range=(0,1))
    with pytest.raises(ValueError):depth.save(tmp_path/'depth.png')
