"""Exercise real TIFF encodings and reject ambiguous acquisition metadata."""
import hashlib
import pytest
np=pytest.importorskip('numpy')
tifffile=pytest.importorskip('tifffile')
from inklet.experimental.tiff import read_tiff


def read(path,**kwargs):
    return read_tiff(path,spacing_zyx=(2,3,4),unit='um',source_id='test acquisition',**kwargs)


@pytest.mark.parametrize('ome',[False,True])
def test_multichannel_timepoint_identity_and_calibration(tmp_path,ome):
    data=np.arange(2*3*4*5*6,dtype='uint16').reshape(2,3,4,5,6)
    path=tmp_path/'source.tif'
    tifffile.imwrite(path,data,ome=ome,photometric='minisblack',metadata={'axes':'TCZYX'})
    with pytest.raises(ValueError,match='explicit time_index'):read(path)
    image=read(path,time_index=1,channel_names=['DNA','Actin','Tubulin'],origin_xyz=(10,20,30))
    for index,(name,channel) in enumerate(image.channels.items()):
        np.testing.assert_array_equal(channel.data,data[1,index])
        assert channel.world((1,2,3))==(22,26,32)
        assert name in channel.source_id and 'time 1' in channel.source_id
        with pytest.raises(ValueError):channel.data.setflags(write=True)
    assert image.report()['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert image.report()['native_axes']=='TCZYX' and not image.report()['axes_override']
    image.channels.clear()
    assert len(image.channels)==3
    with pytest.raises(ValueError,match='out of range'):read(path,time_index=2)


def test_imagej_zcyx_preserves_channels(tmp_path):
    path=tmp_path/'imagej.tif';data=np.arange(2*2*5*6,dtype='uint16').reshape(2,2,5,6)
    tifffile.imwrite(path,data,imagej=True,metadata={'axes':'ZCYX'})
    image=read(path)
    np.testing.assert_array_equal(image.channels['channel-1'].data,data[:,1])
    assert image.report()['source_shape']==list(data.shape)


def test_scalar_2d_and_explicit_ambiguous_stack_axes(tmp_path):
    path=tmp_path/'scalar.tif';data=np.arange(5*6,dtype='uint16').reshape(5,6)
    tifffile.imwrite(path,data,photometric='minisblack')
    np.testing.assert_array_equal(read(path).volumes[0].data,data[None])
    with pytest.raises(ValueError,match='without a T'):read(path,time_index=0)
    stack=np.stack([data,data+1]);tifffile.imwrite(path,stack,photometric='minisblack',metadata=None)
    with pytest.raises(ValueError,match='axes'):read(path)
    image=read(path,axes='ZYX')
    np.testing.assert_array_equal(image.volumes[0].data,stack)
    assert image.report()['axes_override']
    for axes in ('XXY','QYX','ZY','ZYXX'):
        with pytest.raises(ValueError,match='axes'):read(path,axes=axes)


def test_rgb_and_invalid_names_or_series_are_rejected(tmp_path):
    path=tmp_path/'rgb.tif';tifffile.imwrite(path,np.zeros((5,6,3),dtype='uint8'),photometric='rgb')
    with pytest.raises(ValueError,match='RGB'):read(path,axes='YXC')
    tifffile.imwrite(path,np.zeros((2,5,6),dtype='uint16'),photometric='minisblack',metadata={'axes':'CYX'})
    for names in ('ab',['same','same'],['one'],['','two']):
        with pytest.raises(ValueError,match='channel_names'):read(path,channel_names=names)
    for index in (-1,True,2):
        with pytest.raises(ValueError,match='series'):read(path,series=index)


def test_external_ome_references_and_missing_planes_are_rejected(tmp_path):
    path=tmp_path/'external.ome.tif'
    xml='''<?xml version="1.0"?><OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06" UUID="urn:uuid:one"><Image ID="Image:0"><Pixels ID="Pixels:0" DimensionOrder="XYZCT" Type="uint16" SizeX="6" SizeY="5" SizeZ="1" SizeC="1" SizeT="1"><Channel ID="Channel:0:0" SamplesPerPixel="1"/><TiffData IFD="0" PlaneCount="1"><UUID FileName="other.tif">urn:uuid:two</UUID></TiffData></Pixels></Image></OME>'''
    tifffile.imwrite(path,np.zeros((5,6),dtype='uint16'),description=xml,metadata=None)
    with pytest.raises(ValueError,match='External-file'):read(path)
    # tifffile normally zero-fills this absent plane; Inklet must reject it.
    xml=xml.replace('SizeZ="1"','SizeZ="2"').replace('<UUID FileName="other.tif">urn:uuid:two</UUID>','')
    tifffile.imwrite(path,np.zeros((5,6),dtype='uint16'),description=xml,metadata=None)
    with pytest.raises(ValueError,match='missing image data'):read(path)
