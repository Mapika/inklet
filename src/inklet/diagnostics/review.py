"""A visual, exportable companion to the existing figure diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from ..core import Diagram,Rect,Vec2
from .rules import Diagnostic


@dataclass(frozen=True)
class FigureReview:
    """All findings plus a numbered overlay, without altering the source figure."""
    diagram: Diagram
    findings: tuple[Diagnostic,...]
    highlighted: int
    source: Diagram | None = None

    def as_dict(self):
        """JSON-ready findings with stable node references and page coordinates."""
        rows=[]
        for index,finding in enumerate(self.findings,1):
            where=finding.where
            coords=([where.x0,where.y0,where.x1,where.y1] if isinstance(where,Rect) else [where.x,where.y] if isinstance(where,Vec2) else None)
            rows.append(dict(number=index,code=finding.code,severity=finding.severity,message=finding.message,targets=list(finding.targets),where=coords,hint=finding.hint))
        return {'findings':rows,'highlighted':self.highlighted,'count':len(rows)}

    def save(self, prefix):
        """Write a numbered SVG overlay and matching JSON finding list."""
        import inklet as i
        prefix=Path(prefix);prefix.parent.mkdir(parents=True,exist_ok=True)
        svg=prefix.with_suffix('.svg');report=prefix.with_suffix('.json')
        i.save_svg(self.diagram,str(svg),text='embed')
        report.write_text(json.dumps(self.as_dict(),indent=2))
        return svg,report

    def save_bundle(self, directory, *, reference=None, sources=(), panels=None,
                    reference_regions=None, dpi=180, caption='Figure comparison'):
        """Export original art, diagnostics, source hashes and an HTML comparison.

        ``sources`` contains mappings with a local ``path`` and optional
        ``sha256``, ``url`` and ``license``. Expected hashes are verified before
        writing. ``panels`` maps names to placed panel diagrams, whose data
        rectangles are recorded independently of their full ink bounds.
        A local PNG/JPEG reference is copied only into the review bundle; it is
        never embedded in the exported scientific figure. This records evidence,
        not a certificate of scientific or visual equivalence.
        ``reference_regions`` optionally maps panel names to normalized
        ``(left, top, right, bottom)`` image coordinates for matched panel crops.
        Without these explicit registrations, panel focus crops only the Inklet
        image; the reference stays whole rather than assuming matching layouts.
        """
        import hashlib
        import html
        import shutil
        import inklet as i
        provenance=[]
        for entry in sources:
            path=Path(entry['path'])
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if entry.get('sha256') is not None and digest!=entry['sha256']:
                raise ValueError(f'source hash mismatch: {path.name}')
            provenance.append({**entry,'path':str(path),'sha256':digest})
        reference_path=None if reference is None else Path(reference)
        if reference_path is not None:
            if reference_path.suffix.lower() not in ('.png','.jpg','.jpeg'):
                raise ValueError('review reference must be a local PNG or JPEG')
            if not reference_path.is_file():raise FileNotFoundError(reference_path)
        areas={}
        for name,node in (panels or {}).items():
            area=i.plot_area(node)
            if area is None:raise ValueError(f'panel {name!r} has no declared plot area')
            areas[str(name)]={'data':[area.x0,area.y0,area.x1,area.y1],
                              'ink':[node.bbox.x0,node.bbox.y0,node.bbox.x1,node.bbox.y1]}
        import math
        regions={str(k):list(v) for k,v in (reference_regions or {}).items()}
        for key,region in regions.items():
            if (reference_path is None or key not in areas or len(region)!=4 or
                not all(math.isfinite(v) for v in region) or
                not 0<=region[0]<region[2]<=1 or not 0<=region[1]<region[3]<=1):
                raise ValueError('reference regions need known panels and normalized nonempty rectangles')
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        art=self.source if self.source is not None else self.diagram
        scene=i.compile_scene(art)
        svg=scene.to_svg(text='embed',background='white')
        (directory/'figure.svg').write_text(svg)
        (directory/'figure.pdf').write_bytes(scene.to_pdf(text='embed'))
        (directory/'figure.png').write_bytes(i.to_png(scene,dpi=dpi,background='white'))
        self.save(directory/'diagnostics')
        manifest={**self.as_dict(),'sources':provenance,'panels':areas,
                  'embedded_images':svg.count('<image'),
                  'reference':None,'reference_regions':regions,'caption':caption}
        left=''
        if reference_path is not None:
            filename='reference'+reference_path.suffix.lower()
            target=directory/filename
            if reference_path.resolve()!=target.resolve():shutil.copyfile(reference_path,target)
            manifest['reference']={'file':filename,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
            left=f'<figure><figcaption>Reference</figcaption><div class="crop"><img id="reference-image" src="{filename}" alt="Reference figure"></div></figure>'
        credits=''.join('<li>'+html.escape(str(p.get('url',p['path'])))+' — '+
                        html.escape(str(p.get('license','license not supplied')))+'</li>' for p in provenance)
        (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
        box=art.bbox
        focus={key:[(p['data'][0]-box.x0)/box.width,(p['data'][1]-box.y0)/box.height,
                    (p['data'][2]-box.x0)/box.width,(p['data'][3]-box.y0)/box.height]
               for key,p in areas.items()}
        payload=json.dumps({'inklet':focus,'reference':regions}).replace('<','\\u003c')
        options=''.join('<option value="'+html.escape(key,quote=True)+'">'+html.escape(key)+'</option>' for key in areas)
        (directory/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Inklet figure review</title>
<style>body{font:16px system-ui;margin:24px}.pair{display:flex;gap:24px}figure{flex:1;min-width:0;margin:0}
img{width:100%}.crop{position:relative;overflow:hidden}figcaption{padding:12px 0}body.wide .pair{min-width:2400px}</style>
<h1>'''+html.escape(str(caption))+'''</h1><p><a href="figure.svg">SVG</a> · <a href="figure.pdf">PDF</a> ·
<a href="diagnostics.svg">Diagnostic overlay</a> · <a href="manifest.json">Provenance and panel bounds</a></p>
<button onclick="document.body.classList.toggle('wide')">Toggle large comparison</button>
<label> Focus panel <select id="panel"><option value="">Whole figure</option>'''+options+'''</select></label>
<p>Panel focus uses declared data rectangles. The reference stays whole unless a corresponding crop was registered.</p>
<div class="pair">'''+left+'''
<figure><figcaption>Inklet</figcaption><div class="crop"><img id="inklet-image" src="figure.png" alt="Inklet figure"></div></figure></div>
<p>Diagnostics are advisory; source hashes do not establish scientific or visual equivalence.</p><ul>'''+credits+'</ul></html>')
        script='''<script>
const regions='''+payload+''';
function focusPanel(){for(const side of ['inklet','reference']){
const img=document.getElementById(side+'-image');if(!img)continue;
const box=regions[side][document.getElementById('panel').value], view=img.parentElement;
img.removeAttribute('style');view.removeAttribute('style');if(!box||!img.naturalWidth)continue;
const w=box[2]-box[0],h=box[3]-box[1];view.style.aspectRatio=(w*img.naturalWidth)/(h*img.naturalHeight);
Object.assign(img.style,{position:'absolute',width:(100/w)+'%',maxWidth:'none',
left:(-box[0]*100/w)+'%',top:(-box[1]*100/h)+'%'});}}
document.getElementById('panel').addEventListener('change',focusPanel);
for(const img of document.images)img.addEventListener('load',focusPanel);
</script>'''
        page=directory/'index.html'
        page.write_text(page.read_text().replace('</html>',script+'</html>'))
        return {key:directory/name for key,name in [('review','index.html'),('manifest','manifest.json'),
                ('svg','figure.svg'),('pdf','figure.pdf'),('png','figure.png')]}


def review_figure(art, *, max_highlights=100, **checks):
    """Run figure checks and return an inspectable numbered diagnostic overlay.

    Reuses ``lint`` rules for text, contrast, clipping, keys and connections.
    Findings remain advisory: they do not infer scientific correctness, change
    the source art or waive publication constraints. All findings remain in the
    report even when the display highlight limit is reached. Accepts lint's
    thresholds and rule selection, including an explicit page rectangle.
    """
    import inklet as i
    from . import lint
    if type(max_highlights) is not int or max_highlights<0:raise ValueError('max_highlights must be a nonnegative integer')
    findings=tuple(lint(art,**checks));nodes=[];shown=0
    for index,finding in enumerate(findings,1):
        if shown>=max_highlights:break
        box=finding.where
        if isinstance(box,Vec2):box=Rect(box.x-1,box.y-1,box.x+1,box.y+1)
        if not isinstance(box,Rect):continue
        color='#b93136' if finding.severity=='error' else '#b46b00'
        nodes.append(i.as_drawn(i.polyline(box.pad(.4).corners,closed=True,stroke=color,stroke_width=.25)).named(f'review-{index}'))
        label=i.tag(str(index),size=2,pad=(.5,.2),fill=color,color='white')
        nodes.append(label.translated(box.x0-label.bbox.x0,box.y0-label.bbox.y1-.5));shown+=1
    return FigureReview(Diagram(children=(art,*nodes),notes={**art.notes,'figure_review':{'count':len(findings),'highlighted':shown}}),findings,shown,art)
