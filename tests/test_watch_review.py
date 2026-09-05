"""Exercise successive, failed and recovered builds in the actual watch process."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest


def test_watch_compares_successes_and_preserves_output_on_failure(tmp_path):
    pytest.importorskip('PIL')
    if os.name != 'posix' or not any(shutil.which(n) for n in ('google-chrome','chromium','chromium-browser')):
        pytest.skip('POSIX and Chromium required for watch integration')
    script=tmp_path/'author.py';output=tmp_path/'out';log=tmp_path/'watch.log'
    source="import inklet as i\ndef make_document():\n d=i.document(width=60,height=30)\n d.add('label',i.component(i.text,'LABEL'))\n return d\n"
    script.write_text(source.replace('LABEL','First'))
    def until(predicate):
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            result=predicate()
            if result: return result
            time.sleep(.1)
        pytest.fail('watch condition timed out: '+log.read_text())
    with log.open('w') as stream:
        process=subprocess.Popen([sys.executable,'-m','inklet','watch',str(script),'--output',str(output),
                                  '--port','0','--interval','.1','--no-pdf-preview','--dpi','100'],
                                 stdout=stream,stderr=stream)
        try:
            url=until(lambda:re.search(r'http://127\.0\.0\.1:\d+/',log.read_text())).group()
            def state():
                with urlopen(url+'status',timeout=2) as response: return json.load(response)
            until(lambda:state()['generation']==1)
            first=(output/'figure.png').read_bytes()
            time.sleep(.5)
            assert state()==dict(generation=1,building=False,error=None)
            script.write_text(source.replace('LABEL','Second'))
            until(lambda:state()['generation']==2)
            assert (output/'figure-previous.png').read_bytes()==first
            manifest=json.loads((output/'figure-manifest.json').read_text())
            assert manifest['revision']['pixel_comparable'] and manifest['revision']['changed_fraction']>0
            good={p.name:p.read_bytes() for p in output.iterdir() if p.is_file()}
            script.write_text("raise RuntimeError('Intentional author error')\n")
            until(lambda:state()['error'])
            assert state()['generation']==2
            assert good=={p.name:p.read_bytes() for p in output.iterdir() if p.is_file()}
            script.write_text(source.replace('LABEL','Recovered'))
            until(lambda:state()['generation']==3)
            assert state()['error'] is None
            assert (output/'figure-previous.png').read_bytes()==good['figure.png']
        finally:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
