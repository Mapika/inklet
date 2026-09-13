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
    return FigureReview(Diagram(children=(art,*nodes),notes={**art.notes,'figure_review':{'count':len(findings),'highlighted':shown}}),findings,shown)
