"""Studio navigation and view changes preserve authored state and drafts."""
import html
import json
import re
import shutil
import subprocess

import pytest
import inklet as i
from inklet.experimental.layout_editor import LayoutEditor


def test_workspace_navigation_drafts_zoom_pan_and_keyboard(tmp_path):
    chrome=shutil.which('google-chrome') or shutil.which('chromium')
    if not chrome:pytest.skip('Chrome/Chromium not installed')
    root=i.composition(130,80)
    root.add('caption',i.module('Measured result'),x=10,y=10)
    root.add('chart',i.plot_spec(x=(0,1),y=(0,2)).line([(0,0),(1,1)],key='response').axes(),x=20,y=35,anchor='area-nw',width=70,height=30)
    editor=LayoutEditor(root);page=editor._html()
    checks='''<script>
    (async()=>{const sleep=()=>new Promise(r=>setTimeout(r,30));async function ready(rev){for(let n=0;n<250;n++){if(state&&state.revision===rev&&!busy&&previewReady)return;await sleep();}throw Error('timeout '+rev+': '+byId('status').textContent);}
    try{await ready(0);const original=state.svg;
    selectTarget('/caption');const x=document.querySelector('[data-group="placement"][data-key="x"]');x.value=18;x.dispatchEvent(new Event('input'));if(byId('apply').disabled||!dirty.size)throw Error('pending feedback');
    if(selectTarget('/chart')||byId('target').value!=='/caption')throw Error('selection lost draft');
    await request('refresh');if(state.revision!==0||!dirty.size)throw Error('refresh lost draft');
    const saveEvent=new MouseEvent('click',{bubbles:true,cancelable:true});byId('save').dispatchEvent(saveEvent);if(!saveEvent.defaultPrevented)throw Error('saved unapplied preview');
    byId('discard').click();if(dirty.size||!byId('apply').disabled)throw Error('discard');
    selectTarget('/chart');byId('search').value='chart';byId('search').dispatchEvent(new Event('input'));if(byId('object-tree').children.length!==1)throw Error('search');byId('search').value='';drawTree();
    document.querySelector('[data-tab="styles"]').click();const colour=document.querySelector('[data-group="styles"][data-key="stroke"]'),picker=colour.parentElement.querySelector('[type=color]');picker.value='#8833aa';picker.dispatchEvent(new Event('input'));if(colour.value!=='#8833aa'||!dirty.size)throw Error('colour picker');
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,bubbles:true}));await ready(1);if(state.targets['/chart'].styles.response.stroke!=='#8833aa')throw Error('shortcut apply');
    const changed=state.svg;setZoom(2);if(zoom!==2||state.svg!==changed||state.revision!==1||byId('stage').clientWidth<=byId('viewport').clientWidth)throw Error('zoom changed authored state');
    // Real pointer capture is reviewed separately; exercise pan handlers here.
    let captured=false;viewport.setPointerCapture=()=>captured=true;viewport.hasPointerCapture=()=>captured;viewport.releasePointerCapture=()=>captured=false;
    byId('pan-tool').click();const left=viewport.scrollLeft;
    viewport.dispatchEvent(new PointerEvent('pointerdown',{pointerId:9,button:0,clientX:200,clientY:200,bubbles:true}));viewport.dispatchEvent(new PointerEvent('pointermove',{pointerId:9,clientX:150,clientY:200,bubbles:true}));viewport.dispatchEvent(new PointerEvent('pointerup',{pointerId:9,bubbles:true}));if(viewport.scrollLeft<=left||pan!==null||state.svg!==changed)throw Error('pan');
    byId('select-tool').click();byId('fit').click();if(zoom!==1||state.revision!==1)throw Error('fit');
    document.dispatchEvent(new KeyboardEvent('keydown',{key:'z',ctrlKey:true,bubbles:true}));await ready(2);if(state.svg!==original)throw Error('shortcut undo');
    byId('help-button').click();if(!byId('help').open)throw Error('help');byId('close-help').click();
    document.body.dataset.workspaceTest=JSON.stringify({ok:true});
    }catch(error){document.body.dataset.workspaceTest=JSON.stringify({error:error.message});}})();</script>'''
    editor._html=lambda:page.replace('</body>',checks+'</body>')
    with editor:
        result=subprocess.run([chrome,'--headless','--no-sandbox','--window-size=1500,950','--dump-dom','--virtual-time-budget=18000',f'--user-data-dir={tmp_path}/chrome',editor.url],capture_output=True,text=True,timeout=45)
    match=re.search(r'data-workspace-test="([^"]+)"',result.stdout);assert match,result.stderr[-2000:]
    report=json.loads(html.unescape(match[1]));assert report.get('ok'),report
