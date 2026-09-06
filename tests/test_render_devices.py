"""Device selection is explicit, and CPU fallback cannot reuse GPU cache keys."""
import pytest
from inklet.three import devices as d
from inklet.three.blender import BlenderError


def inventory():
    return {'host':{'machine':'test'},'backends':{
        'OPTIX':{'devices':[{'id':'optix-0','name':'NVIDIA test'}]},
        'CUDA':{'devices':[{'id':'cuda-0','name':'NVIDIA test'},{'id':'cuda-1','name':'Second GPU'}]}}}


def test_auto_prefers_gpu_and_respects_exact_device_ids(monkeypatch):
    monkeypatch.setattr(d,'_inventory',lambda *a,**k:inventory())
    auto=d.device_options('AUTO',None,'cpu',None,timeout=10)
    selected=d.device_options('CUDA',['cuda-1'],'error',None,timeout=10)
    assert auto['backend']=='OPTIX'
    assert selected['devices']==[{'id':'cuda-1','name':'Second GPU'}]
    assert d.device_options('AUTO',['cuda-0'],'cpu',None,timeout=10)['backend']=='CUDA'
    assert d.device_options('CPU',None,'cpu',None,timeout=10)['backend']=='CPU'


def test_missing_gpu_falls_back_with_reason_or_raises(monkeypatch):
    monkeypatch.setattr(d,'_inventory',lambda *a,**k:{'backends':{}})
    fallback=d.device_options('AUTO',None,'cpu',None,timeout=10)
    assert fallback['backend']=='CPU' and fallback['requested']=='AUTO'
    assert fallback['fallback_reason']
    with pytest.raises(BlenderError,match='No matching'):
        d.device_options('CUDA',None,'error',None,timeout=10)
    def broken(*a,**k):raise BlenderError('driver probe failed')
    monkeypatch.setattr(d,'_inventory',broken)
    assert 'driver probe failed' in d.device_options('AUTO',None,'cpu',None,timeout=10)['fallback_reason']


@pytest.mark.parametrize('device,ids,fallback',[
    ('GPU',None,'cpu'),('CPU',['gpu-1'],'cpu'),('CUDA','gpu-1','cpu'),
    ('CUDA',['gpu-1','gpu-1'],'cpu'),('CUDA',None,'silent')])
def test_invalid_selection_does_not_start_blender(device,ids,fallback):
    with pytest.raises(ValueError):d.device_options(device,ids,fallback,None,timeout=10)
