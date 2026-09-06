"""Standalone, offline review UI for figure diagnostics and saved revisions."""
import html
import json
from urllib.parse import quote


def review_page(metadata, diagnostics, report, svg):
    esc=html.escape
    files=metadata['files']; name=metadata['name']
    def preview(label,key):
        return (f'<figure><figcaption>{esc(label)}</figcaption><a href="{quote(files[key])}">'
                f'<img src="{quote(files[key])}" alt="{esc(label)}" loading="lazy"></a></figure>')
    links=' · '.join(f'<a href="{quote(files[k])}">{label}</a>' for k,label in
                    [('svg','SVG'),('pdf','PDF'),('png','PNG'),('manifest','Metadata')])
    renderer='resvg' if metadata.get('png_backend')=='resvg' else 'Chromium'
    previews=preview(f'SVG rendered by {renderer}','png')
    if 'pdf_png' in files: previews+=preview('PDF rendered by Poppler','pdf_png')
    revision=''
    if previous:=metadata.get('revision'):
        caption=(f"Previous: {previous['previous_width_mm']:.2f} × {previous['previous_height_mm']:.2f} mm, "
                 f"{previous['previous_dpi']:g} dpi.")
        revision=f'<h2>Revision comparison</h2><p>{esc(caption)}</p>'
        if previous['pixel_comparable']:
            revision+=(f'<p>{previous["changed_fraction"]:.3%} of pixels changed by more than 25/255 in any RGB channel. '
                       'Difference image amplified 5×.</p>'
                       '<label for="revision-opacity">Current revision opacity</label> '
                       '<input id="revision-opacity" type="range" min="0" max="100" value="50">'
                       '<output id="opacity-value" for="revision-opacity">50%</output>'
                       f'<div class="revision-overlay"><img src="{quote(files["previous_png"])}" alt="Previous revision">'
                       f'<img id="revision-current" src="{quote(files["png"])}" alt="Current revision"></div>'
                       '<details><summary>Difference image</summary>'+preview('Pixel differences','revision_diff')+'</details>')
        else:
            revision+=f'<p>{esc(previous["comparison_note"])}</p><div class="previews">'+preview('Previous revision','previous_png')+preview('Current revision','png')+'</div>'
    paths=set(); findings=[]
    for finding in diagnostics:
        components=finding['components']
        for path in components:
            parts=path.split(' / ')
            paths.update(' / '.join(parts[:n]) for n in range(1,len(parts)+1))
        where=finding['where'];bounds=None
        if where and 'x0' in where: bounds=[where[k] for k in ('x0','y0','x1','y1')]
        elif where and 'x' in where: bounds=[where['x']-1,where['y']-1,where['x']+1,where['y']+1]
        label=f"{finding['severity'].upper()} {finding['code']}: {finding['message']}"
        if components: label=' · '.join(components)+' — '+label
        attrs=f'data-severity="{esc(finding["severity"],quote=True)}" data-components="{esc(json.dumps(components),quote=True)}"'
        body=esc(label)
        if bounds: body=f'<button class="finding" data-box="{esc(json.dumps(bounds),quote=True)}">{body}</button>'
        findings.append(f'<li class="diagnostic" {attrs}>{body}</li>')
    panels=''.join(f'<option value="{esc(p,quote=True)}">{esc(p)}</option>' for p in sorted(paths))
    severities=''.join(f'<option value="{esc(s,quote=True)}">{esc(s.title())}</option>' for s in sorted({d['severity'] for d in diagnostics}))
    svg=svg[svg.index('<svg'):]
    return f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{esc(name)} — Inklet review</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:1600px;margin:32px auto;padding:0 24px;color:#222}}
.previews{{display:flex;gap:24px;align-items:flex-start}}figure{{flex:1;min-width:0;margin:0}}img{{width:100%;height:auto;border:1px solid #ddd;box-sizing:border-box}}
figcaption{{margin:12px 0}}#vector svg{{width:100%;height:500px}}button{{cursor:pointer}}.finding{{text-align:left;background:none;border:0;color:#164d91;text-decoration:underline;font:inherit}}
pre{{white-space:pre-wrap;background:#f5f5f5;padding:16px;overflow-wrap:anywhere}}.filters{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:16px 0}}.filters label{{max-width:100%;min-width:0}}select,input{{font:inherit;max-width:100%}}select{{max-width:min(450px,100%)}}
.revision-overlay{{position:relative;margin:16px 0;max-width:1000px}}.revision-overlay img{{display:block}}#revision-current{{position:absolute;inset:0;opacity:.5}}
@media(max-width:800px){{.previews{{display:block}}}}
</style>
<h1>{esc(name)}</h1><p>{links}</p>
<p>{metadata['width_mm']:.2f} × {metadata['height_mm']:.2f} mm · {metadata['dpi']:g} dpi previews · {esc(metadata['text'])} text</p>
<div class="previews">{previews}</div>{revision}
<details id="inspection"><summary>Inspect editable SVG</summary><button id="reset-view">Reset view</button><div id="vector">{svg}</div></details>
<h2>Diagnostics</h2>
<div class="filters"><label>Panel or component <select id="panel-filter"><option value="">All components</option>{panels}</select></label>
<label>Severity <select id="severity-filter"><option value="">All severities</option>{severities}</select></label>
<label>Search <input id="diagnostic-search" type="search" placeholder="Code or message"></label><button id="clear-filters">Clear filters</button></div>
<p id="finding-count" role="status" aria-live="polite"></p><ul id="findings">{''.join(findings)}</ul>
<details><summary>Complete diagnostic report</summary><pre>{esc(report)}</pre></details>
<script>
const vector=document.querySelector('#vector svg'),original=vector.getAttribute('viewBox');
document.getElementById('reset-view').onclick=()=>{{vector.setAttribute('viewBox',original);document.getElementById('inklet-review-highlight')?.remove()}};
for(const button of document.querySelectorAll('.finding'))button.onclick=()=>{{
  document.getElementById('inspection').open=true;
  const [x0,y0,x1,y1]=JSON.parse(button.dataset.box),w=x1-x0,h=y1-y0;
  vector.setAttribute('viewBox',[x0-4,y0-4,w+8,h+8].join(' '));
  document.getElementById('inklet-review-highlight')?.remove();
  const mark=document.createElementNS('http://www.w3.org/2000/svg','rect');
  for(const [k,v] of Object.entries({{id:'inklet-review-highlight',x:x0,y:y0,width:Math.max(w,.2),height:Math.max(h,.2),fill:'none',stroke:'#d22','stroke-width':'.2','pointer-events':'none'}}))mark.setAttribute(k,v);
  vector.append(mark);vector.scrollIntoView({{block:'center',behavior:'smooth'}});
}};
const panel=document.getElementById('panel-filter'),severity=document.getElementById('severity-filter'),search=document.getElementById('diagnostic-search'),rows=[...document.querySelectorAll('.diagnostic')];
function filter(){{let visible=0;for(const row of rows){{
  const matches=JSON.parse(row.dataset.components).some(p=>p===panel.value||p.startsWith(panel.value+' / '));
  row.hidden=(panel.value&&!matches)||(severity.value&&row.dataset.severity!==severity.value)||!row.textContent.toLowerCase().includes(search.value.toLowerCase());
  if(!row.hidden)visible++;
}}document.getElementById('finding-count').textContent=`${{visible}} of ${{rows.length}} findings`}}
for(const input of [panel,severity,search]){{input.addEventListener('input',filter);input.addEventListener('change',filter)}}
document.getElementById('clear-filters').onclick=()=>{{panel.value=severity.value=search.value='';filter()}};filter();
const opacity=document.getElementById('revision-opacity');
if(opacity)opacity.oninput=()=>{{document.getElementById('revision-current').style.opacity=opacity.value/100;document.getElementById('opacity-value').textContent=opacity.value+'%'}};
</script></html>'''
