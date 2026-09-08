"""Complete real-map workflow acceptance, including replacement and resizing."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest
from inklet.experimental.selection import SelectionState
from inklet.core import DiagramError

RECIPE=Path(__file__).resolve().parents[1]/'examples/v4/regional_report.py'
spec=importlib.util.spec_from_file_location('regional_report',RECIPE)
recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)


def test_real_geometry_country_series_and_derived_comparisons():
    figure=recipe.make_scene();payload=figure.payload();table=figure.table
    assert len(table.row_ids)==18 and len(payload['layers'])==6
    assert sum(len(m['geometry'][0]) for m in payload['layers'][0]['marks'])>500
    assert payload['layers'][0]['projection']=='plate-carree'
    history=payload['layers'][1]
    assert history['missing']==1
    hungary=[m for m in history['marks'] if m['ids'][0]=='HUN']
    assert len([m for m in hungary if m['kind']=='circle'])==11
    assert len([m for m in hungary if m['kind']=='line'])==9
    assert not any(m['samples'][0]['column']=='month_05' and m['samples'][1]['column']=='month_07'
                   for m in hungary if m['kind']=='line')
    assert payload['layers'][2]['statistics']['n']==18
    for n,key in enumerate(table.row_ids):
        assert table.columns['change'][n]==round(table.columns['month_12'][n]-table.columns['month_01'][n],1)


def test_selection_reopen_replace_remove_and_two_physical_widths(tmp_path):
    original=recipe.make_scene();table=original.table
    visible=[key for key,group in zip(table.row_ids,table.columns['group']) if group=='Central']
    state=original.state(SelectionState.for_table(table,selected=['HUN','EST'],visible=visible))
    saved=json.loads(json.dumps(state));assert recipe.make_scene().to_svg(saved)==original.to_svg(state)
    changed=recipe.make_table(revised=True)
    with pytest.raises(ValueError):original.replace_data(changed,views=recipe.make_views(changed),state=saved)
    revision=original.replace_data(changed,views=recipe.make_views(changed),state=saved,missing='drop')
    report=revision.report()
    assert report['removed_ids']==['EST'] and report['changed_ids']==['HUN']
    for width in (160,210):
        export=revision.figure.replace_data(changed,state=revision.state(),width=width)
        selection,viewport=export.figure.validate_state(export.state())
        assert selection.selected_ids==('HUN',) and set(selection.visible_ids)==set(visible)
        svg=ET.fromstring(export.figure.to_svg(export.state()))
        assert float(svg.attrib['width'][:-2])==width
        assert export.figure.payload()['layers'][2]['statistics']['n']==17
    assert original.payload()['layers'][2]['statistics']['n']==18


def test_csv_roundtrip_derivation_and_cli_restore(tmp_path):
    table=recipe.make_table();path=tmp_path/'data.csv';recipe.write_table(table,path)
    assert recipe.read_table(path).digest==table.digest
    figure=recipe.make_scene();state=figure.state(SelectionState.for_table(table,selected=['HUN']))
    (tmp_path/'view.json').write_text(json.dumps(state))
    import sys
    command=[sys.executable,str(RECIPE),'--state',str(tmp_path/'view.json'),'--output',str(tmp_path/'restored')]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert (tmp_path/'restored/figure.svg').read_text()==figure.to_svg(state)
    result=subprocess.run([sys.executable,str(RECIPE),'--revised','--rebase-state',str(tmp_path/'view.json'),
                           '--output',str(tmp_path/'revised')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads((tmp_path/'revised/revision.json').read_text())['changed_ids']==['HUN']
    result=subprocess.run([sys.executable,str(RECIPE),'--csv',str(path),'--output',str(tmp_path/'supplied')],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    provenance=json.loads((tmp_path/'supplied/provenance.json').read_text())
    assert provenance['data_digest']==table.digest
    assert 'User-supplied measurements' in provenance['credit'] and 'SHA-256' in provenance['credit']


@pytest.mark.parametrize('change', ['duplicate','header','invalid','infinite','negative','group','short','long','empty'])
def test_bad_csv_reports_error(tmp_path,change):
    path=tmp_path/'data.csv';recipe.write_table(recipe.make_table(),path);lines=path.read_text().splitlines()
    cells=lines[1].split(',')
    if change=='duplicate':lines.append(lines[1])
    elif change=='header':lines[0]+=',id'
    elif change=='invalid':cells[3]='bad'
    elif change=='infinite':cells[3]='inf'
    elif change=='negative':cells[3]='-1'
    elif change=='group':cells[2]='unknown'
    elif change=='short':cells.pop()
    elif change=='long':cells.append('extra')
    elif change=='empty':lines=lines[:1]
    if len(lines)>1:lines[1]=','.join(cells)
    path.write_text('\n'.join(lines)+'\n')
    with pytest.raises(ValueError):recipe.read_table(path)


def test_optional_svg_pdf_is_one_physical_vector_page(tmp_path):
    if not shutil.which('google-chrome') or not shutil.which('pdfinfo') or not shutil.which('pdfimages'):
        pytest.skip('Chrome and Poppler required')
    from inklet.render.preview import svg_pdf
    source=tmp_path/'figure.svg';source.write_text(recipe.make_scene(width=160).to_svg())
    output=svg_pdf(source,tmp_path/'figure.pdf')
    report=subprocess.check_output(['pdfinfo',str(output)],text=True)
    import re
    assert re.search(r'Pages:\s+1\b',report)
    width,height=map(float,re.search(r'Page size:\s+([\d.]+) x ([\d.]+)',report).groups())
    assert width==pytest.approx(160*72/25.4,abs=.8)
    expected=float(ET.parse(source).getroot().attrib['height'][:-2])
    assert height==pytest.approx(expected*72/25.4,abs=.8)
    # Native vector plots must not be flattened into a full-page image.
    images=subprocess.check_output(['pdfimages','-list',str(output)],text=True).strip().splitlines()
    assert len(images)==2
    if shutil.which('pdftoppm'):
        Image=pytest.importorskip('PIL.Image')
        from PIL import ImageChops, ImageStat
        from inklet.render.preview import svg_png, pdf_png
        svg_png(source,tmp_path/'svg.png',dpi=150);pdf_png(output,tmp_path/'pdf.png',dpi=150)
        a,b=(Image.open(tmp_path/(name+'.png')).convert('RGB') for name in ('svg','pdf'))
        assert abs(a.width-b.width)<=1 and abs(a.height-b.height)<=1
        box=(0,0,min(a.width,b.width),min(a.height,b.height))
        # Independent PDF rasterization must preserve the actual plots. Allow
        # subpixel print-page rounding and different edge antialiasing.
        assert max(ImageStat.Stat(ImageChops.difference(a.crop(box),b.crop(box))).mean)<3
    source.write_text('<svg width="nanmm" height="10mm"/>')
    with pytest.raises(DiagramError,match='positive physical'):svg_pdf(source,output)


REGIONAL_CHECKS = r"""
(async()=>{
 await inkletDocument.ready;const ok=(c,m)=>{if(!c)throw Error(m);};
 let r=inklet;const map=r.scene.layers[0],b=map.clip,e=map.extent;
 const hit=r.pick(b[0]+(19-e[0])/(e[2]-e[0])*b[2],b[1]+(e[3]-47)/(e[3]-e[1])*b[3],0);
 ok(hit?.id==='HUN','real map picking at Hungary');
 const filter=document.getElementById('id-filter');filter.value='Central';filter.dispatchEvent(new Event('input'));
 ok(r.visible.size===6,'group search');
 document.querySelector('button[aria-label="Select HUN"]')?.click();
 // The table button selects all marks with this country identity.
 ok(r.selected.has('HUN'),'table selection');
 const before={state:r.state(),svg:r.exportSVG()};
 r.select(['HUN','EST']);let rejected=false;
 try{await inkletDocument.switchRevision(1);}catch(e){rejected=true;}
 ok(rejected&&inklet===r,'removed selection did not keep current scene');
 const report=await inkletDocument.switchRevision(1,{missing:'drop'});r=inklet;
 ok(report.removed_selected.join(',')==='EST'&&report.changed_ids.join(',')==='HUN','revision report');
 ok(r.selected.has('HUN')&&r.visible.size===6,'revision retained state');
 ok(r.scene.layers[2].statistics.n===17,'distribution did not rebuild');
 const n=r.rowIndex.get('HUN');ok(r.scene.columns.latest[n]===88.3,'replacement estimate');
 const circle=r.items.find(m=>m.layer.name==='history'&&m.id==='HUN'&&m.sample?.column==='month_12');
 ok(circle.sample.y===88.3,'history revision');
 r.setViewport([5,4,r.scene.width/1.5,r.scene.height/1.5]);const state=r.state();
 r.select([]);r.loadState(state);ok(r.selected.has('HUN'),'reopen revision');
 return {before,after:{state:r.state(),svg:r.exportSVG()}};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
"""


def test_complete_browser_workflow_and_reconstructed_pixels(tmp_path):
    from test_browser_series import browser_result
    from test_browser_statistics import svg_geometry
    from inklet.experimental.browser import RevisionOption
    original=recipe.make_scene();revised=recipe.make_scene(revised=True)
    result=browser_result(tmp_path,original,REGIONAL_CHECKS,search_columns=('country','group'),
        revisions=[RevisionOption('Revised',revised,recipe.CREDIT,search_columns=('country','group'))])
    for name,figure in [('before',original),('after',revised)]:
        exported=result[name]
        assert svg_geometry(figure.to_svg(exported['state']))==svg_geometry(exported['svg'])
    Image=pytest.importorskip('PIL.Image')
    from PIL import ImageChops
    from inklet.render.preview import svg_png
    for name,svg in [('python',revised.to_svg(result['after']['state'])),('browser',result['after']['svg'])]:
        source=tmp_path/(name+'.svg');source.write_text(svg);svg_png(source,tmp_path/(name+'.png'),dpi=150)
    a,b=(Image.open(tmp_path/(name+'.png')).convert('RGB') for name in ('python','browser'))
    assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None
