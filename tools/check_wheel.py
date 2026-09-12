"""Install a wheel with core dependencies and exercise public authoring/export APIs."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import venv

SCRIPT = '''from importlib.metadata import version
from importlib.util import find_spec
from pathlib import Path
import sys
import inklet as i
assert i.__version__ == version("inklet")
assert Path(i.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert find_spec("PIL") is None and find_spec("numpy") is None
assert find_spec("resvg_py") is None
from inklet.experimental.browser import GeoFeatures, MapView, BrowserFigure
from inklet.experimental.selection import KeyedTable
geography = GeoFeatures((('route','LineString',((0,0),(1,1))),('stop','Point',(1,1))), attribution='Original smoke fixture')
geographic = BrowserFigure(KeyedTable('assets',dict(id=['route','stop'])),[MapView('map',geography,(-1,-1,2,2))])
assert [mark['kind'] for mark in geographic.payload()['layers'][0]['marks']] == ['line','circle']
assert 'Original smoke fixture' in geographic.to_html(renderer='compiled') and '<line' in geographic.to_svg()
response = i.Series('Response',[0,1],[1,2],'#34786b',[.8,1.8],[1.2,2.2])
layer = i.plot_spec().series(response,key='response')
recipe = i.plot_spec(x=(0,1),y=(0,3)).extend(layer).axes(x_options={'count':3},y_options={'count':4})
variant = recipe.copy().style('response',color='#aa5b36',name='Variant')
comparison = i.document(width=120,columns=2)
comparison.add('original',recipe,row=0,column=0)
comparison.add('variant',variant,row=0,column=1)
assert '#aa5b36' in comparison.compile().to_svg()
assert response.name == 'Response'
packed = i.panel(40,30,x=(0,1),y=(0,1))
packed.scatter([(k/300,.5) for k in range(300)],size=.3,color='blue')
viewer = i.compile_scene(packed.build()).to_html()
assert 'class CompiledSceneViewer' in viewer and 'drawArraysInstanced' in viewer
assert 'class MarkerIndex' in viewer and 'texelFetch' in viewer
assert 'inklet.compiled-viewer/1' in viewer and '/*SCENE*/' not in viewer
from inklet.experimental.selection import KeyedTable
assert find_spec("pandas") is None and find_spec("polars") is None
for adapter, extra in ((KeyedTable.from_pandas, 'pandas'), (KeyedTable.from_polars, 'polars')):
    try:
        adapter('missing-extra', None)
    except ImportError as error:
        assert 'inklet[' + extra + ']' in str(error)
    else:
        raise AssertionError('Table adapter silently loaded an optional dependency')
from inklet.experimental.browser import BrowserScatter, ScatterView, BrowserFigure, LineView, BarView, GeoRegions, RegionView, RevisionOption, FacetView
keyed = KeyedTable('wheel', {'id':['a','b'], 'x':[0,1], 'y':[1,2]})
linked_figure = BrowserFigure(keyed, [ScatterView('points', 'x', 'y', (0,1), (0,3))])
visual_overrides = linked_figure.overrides({'points': {'radius_mm': 1.2}})
assert 'r="1.2"' in linked_figure.to_svg(overrides=visual_overrides)
linked_compiled = linked_figure.to_html(renderer='compiled', backend='auto', overrides=visual_overrides)
assert 'class CompiledFigureRenderer' in linked_compiled and 'class CompiledSceneViewer' in linked_compiled
assert 'setMarkerVisibility' in linked_compiled and '/*RENDERER_ADAPTER*/' not in linked_compiled
assert 'inklet.visual-overrides/0.1' in linked_compiled and 'id="edit-undo"' in linked_compiled
assert '/*EDITOR_RUNTIME*/' not in linked_compiled
from inklet.experimental.browser import TimeAxis
from inklet.experimental.measurement import LabelImage
from inklet.experimental.browser import LabelImageView
label_image=LabelImage([[1,3]],[[1,1]],[('region',1)],(.5,.5),'um')
assert label_image.table().columns['area']==(.5,) and label_image.table().columns['mean']==(2.,)
image_scene=BrowserFigure(label_image.table(),[LabelImageView('image',label_image,(0,4),.5)])
assert 'data:image/png;base64,' in image_scene.to_svg() and 'image-status' in image_scene.to_html()
from inklet.experimental.browser import DrawingItem, DrawingView
from inklet.experimental.engineering import BoxAssembly, BoxComponent
assembly = BoxAssembly([BoxComponent('a',(2,4,6),(0,0,0))], 'mm')
assert assembly.section('y',0) == (('a',(-1,-3,1,3)),)
drawing_scene = BrowserFigure(keyed,[DrawingView('native',lambda t,w,h:[DrawingItem(('a',),i.box('A',width=10,height=8).translated(w/2,h/2))])])
assert 'data:image/svg+xml;base64,' in drawing_scene.to_svg()
assert drawing_scene.payload()['layers'][0]['drawing']['omitted_ids'] == ['b']
from inklet.experimental.browser import ECDFView, IntervalView, SeriesView
series_scene = BrowserFigure(keyed,[SeriesView('series',[(1,'x'),(2,'y')],(0,3),(0,3))])
assert len(series_scene.payload()['layers'][0]['marks']) == 6
assert 'samples' in series_scene.to_html() and '<line' in series_scene.to_svg()
statistics_table = KeyedTable('statistics',dict(id=['a','b'],x=[1,2],y=[2,3],lo=[1,None],hi=[3,None]))
statistics_scene = BrowserFigure(statistics_table,[ECDFView('cdf','y',(0,4)),
    IntervalView('interval','x','y',(0,3),(0,4),lower='lo',upper='hi',interval_label='Supplied illustrative range')])
assert statistics_scene.payload()['layers'][0]['statistics']['n'] == 2
assert 'statistics-status' in statistics_scene.to_html() and '<circle' in statistics_scene.to_svg()
timed = KeyedTable('dates', {'id':['a','b'], 'day':['2024-02-29','2024-03-01'], 'value':[1,2]})
time_scene = BrowserFigure(timed, [LineView('time','day','value',TimeAxis(('2024-02-28','2024-03-02')),(0,3),max_gap_seconds=86400)])
assert time_scene.payload()['layers'][0]['time_gaps'] == 0
assert '<line' in time_scene.to_svg() and ' / UTC' not in time_scene.to_html()
browser_scene = BrowserScatter(keyed, [ScatterView('scatter','x','y',(0,1),(0,3))])
assert 'class ScatterRenderer' in browser_scene.to_html()
assert '<circle' in browser_scene.to_svg()
mixed = BrowserFigure(keyed, [LineView('line','x','y',(0,1),(0,3)),
                             BarView('bar','x','y',(-1,2),(0,3))])
assert '<line' in mixed.to_svg() and '<rect' in mixed.to_svg()
assert 'class ScatterRenderer' in mixed.to_html(state=mixed.state())
revision = mixed.replace_data(KeyedTable('wheel', {'id':['b','c'], 'x':[1,2], 'y':[3,2]}))
assert revision.report()['changed_ids'] == ['b'] and revision.report()['removed_ids'] == ['a']
assert '<rect' in revision.figure.to_svg(revision.state())
assert 'class ScatterRenderer' in revision.figure.to_html(state=revision.state())
switchable = mixed.to_html(revisions=[RevisionOption('Revised',revision.figure,'Synthetic wheel fixture.')])
assert 'switchRevision' in switchable and '/*REVISION_CATALOG*/' not in switchable
facet_table = KeyedTable('facets', {'id':['a','b'], 'x':[0,1], 'y':[1,2], 'group':['A','B']})
faceted = BrowserFigure(facet_table, [FacetView(ScatterView('points','x','y',(0,1),(0,3)), 'group', ('A','B','Empty'))])
assert len(faceted.payload()['layers']) == 3 and not faceted.payload()['layers'][2]['points']
assert 'facet-status' in faceted.to_html() and '<circle' in faceted.to_svg()
regions = GeoRegions((('a', ((((0,0),(1,0),(1,1),(0,1),(0,0)),),)),
                      ('b', ((((1,0),(2,0),(2,1),(1,1),(1,0)),),))))
region_scene = BrowserFigure(keyed, [RegionView('map',regions,(0,0,2,1))])
assert 'evenodd' in region_scene.to_svg() and 'polygonContains' in region_scene.to_html()
Path('table.csv').write_text('x,y\\n0,1\\n1,2\\n')
table = i.read_csv('table.csv', types={'x': int, 'y': float}, method='simulated')
assert table.columns['y'] == (1., 2.) and table.source.sha256
from inklet.experimental.volume import Volume
from inklet.experimental.sections import Plane
plane = Plane((0,0,0), (1,0,0), (0,1,0), (10,20), (.1,.1), 'um')
assert plane.extent == (2,1)
from inklet.experimental.slabs import Slab
from inklet.experimental.regions import BoxRegion
slab = Slab(plane, .5, 5)
region = BoxRegion('wheel-region', (-1,-1,-1), (1,1,1), 'um')
assert len(region.edges) == 12 and len(region.intersection(plane)) == 4
assert region.outline(plane, width=40).width >= 40
assert slab.report()['samples'] == 5
from inklet.experimental.channels import Channel, Composite
from inklet.experimental.contours import LabelContour
from inklet.experimental.measurements import LabelMeasurements, measure_labels
from inklet.experimental.tiff import TiffImage, read_tiff
assert find_spec("numpy") is None
try:
    Volume([[[1]]], (1,1,1), 'um', source_id='wheel')
except ImportError as error:
    assert 'inklet[volume]' in str(error)
else:
    raise AssertionError('Volume silently imported optional numerical dependencies')
assert set(i.scene_templates())=={'laboratory','product','architecture'}
assert (Path(i.__file__).parent/'three/blender/template_worker.py').is_file()
import struct
depth = i.ScenePass('depth', (1, 1), 1, 10, 10, struct.pack('<f', 2.5))
assert depth.value(0, 0) == 2.5
from inklet.experimental.figure_planner import Length, Region, Target, View, plan
snapshot = i.SceneRender(i.spacer(10, 10), dict(width_mm=10, height_mm=10,
    pixels=[1,1], projection=dict(type='ORTHO', bounds=[-2,2,-2,2], near=.1, far=20,
    world_to_camera=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])), False, {'depth': depth})
planned = plan([Target('point', 'Point', (0,0,-1),
    region=Region(((-1,0,-1),(1,0,-1)),1,5))], [View('front', snapshot)], crossing_penalty=25)
assert planned.feasible and planned.placements[0].visible is True
assert '<text' in i.to_svg(planned.diagram())
assert i.to_pdf(planned.diagram()).startswith(b'%PDF')
assert planned.report()['constraints']['selected_regions']['point']['visible_fraction'] == 1
revised = plan([Target('point', 'Point', (1,0,-1))], [View('front', snapshot)],
               previous=planned, displacement_penalty=10, max_displacement_mm=0)
assert revised.feasible and revised.label_positions() == planned.label_positions()
assert abs(sum(revised.report()['score_terms'].values())-revised.score) < 1e-9
assert Length.between((0,0,0), (3,4,0), metres_per_unit=.001).label('mm') == '5 mm'
assert i.render_quality('final').samples == 256
try:
    depth.to_numpy()
except i.DiagramError as error:
    assert 'inklet[images]' in str(error)
else:
    raise AssertionError('Pass arrays unexpectedly imported NumPy')
def make_document():
    data = i.dataset({"x": [0, 1, 2], "y": [1, 3, 2]}, name="wheel smoke")
    p = i.plot_spec(x=(0, 2), y=i.shared_scale(data.column("y")))
    p.line(data.points("x", "y")).axes(x="Time", y="Value")
    panels = i.subfigure().letters()
    panels.add("response", p)
    art = i.composition(100, 25)
    art.add("input", i.module("Input"), x=2, y=3)
    x, y = art.point("input", "out")
    art.add("output", i.module("Output"), x=x+10, y=3)
    art.link("input:out", "output:in")
    doc = i.publication("single-column", width=110).document()
    doc.add("architecture", art, min_height=30)
    doc.add("panels", panels)
    return doc
if __name__ == "__main__":
    compiled = make_document().compile()
    compiled.save("smoke.svg", "smoke.pdf")
    assert Path("smoke.pdf").read_bytes().startswith(b"%PDF")
    assert "<svg" in Path("smoke.svg").read_text()
    assert compiled.metadata["datasets"][0]["name"] == "wheel smoke"
    preset_doc = i.preset("educational.textbook").document()
    preset_doc.add("plot", i.plot_spec(x=(0, 1), y=(0, 1)).line([(0, 0), (1, 1)]).axes())
    before = preset_doc.compile()
    preset_doc.use_preset("marketing.report")
    after = preset_doc.compile()
    assert before.to_svg() != after.to_svg()
    assert after.metadata["preset"]["name"] == "marketing.report"
    assert after.to_pdf().startswith(b"%PDF")
    brush = i.LinearGradient(((0, "white"), (1, "#245b8a")))
    painted = i.paint(i.circle(width=15, height=15), brush)
    assert "linearGradient" in i.to_svg(painted)
    assert b"/ShadingType 2" in i.to_pdf(painted)
    try:
        i.to_png(painted)
    except i.DiagramError as error:
        assert "inklet[render]" in str(error)
    else:
        raise AssertionError("PNG unexpectedly works without its optional renderer")
    with i.RenderQueue(max_workers=1): pass
    assert i.RenderProgress('queued','Waiting').fraction is None
    print("Installed wheel API passed", i.__version__)
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel',type=Path)
    args=parser.parse_args();wheel=args.wheel.resolve()
    if not wheel.is_file():parser.error(f'wheel not found: {wheel}')
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','PYTHONSTARTUP','VIRTUAL_ENV')}
    with tempfile.TemporaryDirectory(prefix='inklet-wheel-') as scratch:
        root=Path(scratch);uv=shutil.which('uv')
        venv.EnvBuilder(with_pip=uv is None).create(root/'env')
        python=root/'env'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        def run(*args):
            subprocess.run([str(python),*map(str,args)],cwd=root,env=env,check=True,timeout=180)
        if uv:
            subprocess.run([uv,'pip','install','--python',str(python),str(wheel)],
                           cwd=root,env=env,check=True,timeout=180)
        else:
            run('-m','pip','install','--disable-pip-version-check',wheel)
        (root/'author.py').write_text(SCRIPT)
        run('author.py')
        run('-m','inklet','doctor')
        run('-m','inklet','build','author.py','--vectors-only','--output','review')
        assert (root/'review/figure.svg').is_file() and (root/'review/figure.pdf').is_file()
    return 0


if __name__=='__main__':raise SystemExit(main())
