"""Quality selection and explicit override precedence without Blender."""
from dataclasses import FrozenInstanceError
import pytest
import inklet as i
from inklet.three.quality import quality_options


def test_quality_presets_are_immutable_and_validate_overrides():
    final=i.render_quality('final')
    assert (final.dpi,final.samples,final.denoise)==(300,256,True)
    with pytest.raises(FrozenInstanceError):final.samples=1
    changed=i.render_quality('final',samples=512)
    assert changed.samples==512 and final.samples==256
    for options in ({'samples':0},{'dpi':float('nan')},{'denoise':1},{'noise_threshold':-1}):
        with pytest.raises(ValueError):i.render_quality('preview',**options)
    with pytest.raises(ValueError):i.render_quality('unknown')


def test_quality_preserves_defaults_and_honours_explicit_settings():
    assert quality_options(None,None,None,None,None)==(None,150,32,None,None)
    q,dpi,samples,denoise,threshold=quality_options('final',72,2,False,0)
    assert q.name=='final' and (dpi,samples,denoise,threshold)==(72,2,False,0)
    with pytest.raises(TypeError):quality_options(4,None,None,None,None)
    with pytest.raises(ValueError):quality_options(None,None,None,None,float('inf'))
