"""The public-data example must never silently accept changed source bytes."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest


@pytest.fixture
def source(tmp_path,monkeypatch):
    path=Path(__file__).resolve().parents[1]/'examples/biology/data.py'
    spec=importlib.util.spec_from_file_location('biology_source',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    payload=b'locked microscopy chunk'
    lock=tmp_path/'lock.json'
    lock.write_text(json.dumps(dict(base_url='https://example.invalid/',files=[
        dict(path='data/0',size=len(payload),sha256=hashlib.sha256(payload).hexdigest()),
        dict(path='data/1',missing=True)])))
    monkeypatch.setattr(module,'LOCK',lock)
    return module,payload,tmp_path/'cache'


def test_fetch_reuses_only_verified_bytes_and_repairs_a_changed_cache(source,monkeypatch):
    module,payload,root=source;requests=[]
    def download(url,timeout):
        requests.append(url)
        return io.BytesIO(payload)
    monkeypatch.setattr(module.urllib.request,'urlopen',download)
    module.fetch(root);module.fetch(root)
    assert requests==['https://example.invalid/data/0']
    (root/'data/0').write_bytes(b'changed')
    module.fetch(root)
    assert len(requests)==2 and (root/'data/0').read_bytes()==payload
    assert not (root/'data/1').exists()
    assert not list(root.rglob('*.part'))


def test_fetch_rejects_changed_remote_bytes(source,monkeypatch):
    module,_,root=source
    monkeypatch.setattr(module.urllib.request,'urlopen',lambda *a,**k:io.BytesIO(b'changed'))
    with pytest.raises(ValueError,match='size/hash changed'):module.fetch(root)
    assert not (root/'data/0').exists()


def test_fetch_rejects_data_where_the_source_records_background(source,monkeypatch):
    module,payload,root=source
    monkeypatch.setattr(module.urllib.request,'urlopen',lambda *a,**k:io.BytesIO(payload))
    (root/'data').mkdir(parents=True);(root/'data/1').write_bytes(b'unexpected')
    with pytest.raises(ValueError,match='absent source chunk'):module.fetch(root)
