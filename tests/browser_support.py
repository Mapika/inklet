"""Shared browser execution and independent export oracles for contract tests."""
import html
import json
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET
import pytest


def browser_result(tmp_path,figure,checks,**html_options):
    browser=next((p for name in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(name))),None)
    if browser is None:pytest.skip('Chrome/Chromium not installed')
    page=tmp_path/'index.html';page.write_text(figure.to_html(**html_options).replace('</html>','<script>'+checks+'</script></html>'))
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S);assert match,result.stdout[-2000:]
    report=json.loads(html.unescape(match[1]));assert 'error' not in report,report
    return report


def svg_geometry(svg):
    root=ET.fromstring(svg); result=[]
    for group in (root[1],root[-1]):
        for element in group.iter():
            tag=element.tag.rsplit('}',1)[-1]
            if tag not in ('line','circle') or ('fill' not in element.attrib and 'stroke' not in element.attrib):continue
            attrs={}
            for key,value in element.attrib.items():
                try:attrs[key]=float(value)
                except ValueError:attrs[key]=value
            result.append((tag,attrs))
    return root.attrib['viewBox'].split(),result


def assert_svg_pixels(tmp_path, python_svg, browser_svg, *, dpi=150):
    """Compare complete rendered artwork; keep SVG/PNG files for failure review."""
    Image = pytest.importorskip('PIL.Image')
    from PIL import ImageChops
    from inklet.render.preview import svg_png
    for name, svg in [('python', python_svg), ('browser', browser_svg)]:
        path = tmp_path / (name + '.svg')
        path.write_text(svg)
        svg_png(path, path.with_suffix('.png'), dpi=dpi)
    with Image.open(tmp_path/'python.png') as a, Image.open(tmp_path/'browser.png') as b:
        assert a.size == b.size
        assert ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox() is None
