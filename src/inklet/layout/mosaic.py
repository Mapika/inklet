"""Named, spanning panels that rebuild to fit without shrinking typography."""
from __future__ import annotations
import math
from dataclasses import dataclass
from collections.abc import Mapping
from ..core import Diagram, DiagramError, Envelope, Rect, mm


@dataclass(frozen=True)
class PanelSpec:
    """Content with minimum outer dimensions and a drawing-area aspect ratio.

    Minimums include panel headers/furniture. ``aspect`` is width / height of
    the factory's drawing region, not its axes or caption. ``align`` chooses
    vertical start/center/end placement. Static diagrams cannot be aspect-fit.
    """
    content: object
    min_width: float = 0
    min_height: float = 0
    aspect: float | None = None
    align: str = 'center'


def _constrained_tracks(initial, requirements):
    """Euclidean projection onto interval minimums and the fixed page budget."""
    n=len(initial);total=sum(initial);x=list(initial)
    constraints=[(tuple(range(n)),total,True)]+[(tuple(range(a,b)),v,False) for a,b,v in requirements]+[((k,),.001,False) for k in range(n)]
    corrections=[[0.]*n for _ in constraints]
    for _ in range(4000):
        previous=x[:]
        for k,(indices,value,equality) in enumerate(constraints):
            y=[a+b for a,b in zip(x,corrections[k])];delta=(value-sum(y[j] for j in indices))/len(indices)
            z=y[:]
            if equality or delta>0:
                for j in indices:z[j]+=delta
            corrections[k]=[a-b for a,b in zip(y,z)];x=z
        if max(abs(a-b) for a,b in zip(x,previous))<1e-9 and abs(sum(x)-total)<1e-7 and all(sum(x[j] for j in indices)>=value-1e-7 for indices,value,_ in constraints):return x
    raise DiagramError('panel minimum sizes cannot fit the page; enlarge it or reduce the requested minimums')


def panel_mosaic(layout, panels, *, width, height, gap=4, margin=4,
                 row_weights=None, column_weights=None, titles=None,
                 letters=True, label_size=4, label_gap=2):
    """Build a page from a rectangular matrix of panel names ('.' is empty).

    Repeated names span a rectangular block. Content is a Diagram, a built
    Panel, or a pure ``factory(width, height)`` returning either. Factories are
    rebuilt with smaller drawing regions when axes or legends exceed their
    allocated outer box. Fonts/strokes are never scaled. Static content that
    cannot fit raises an informative error. Factories may run up to 12 times.

    Titles and panel letters occupy a reserved header band. Returns a Diagram
    with a top-left page origin and named panel/content boxes in
    ``notes['panel_mosaic']``. This is a static composition; use Composition
    slots when live data binding or interactive layout edits are needed.
    """
    import inklet as i
    rows=[row.split() if isinstance(row,str) else list(row) for row in layout]
    if not rows or not rows[0] or any(len(r)!=len(rows[0]) for r in rows):
        raise ValueError('panel_mosaic layout must be a nonempty rectangular matrix')
    if any(not isinstance(k,str) or not k for r in rows for k in r):
        raise ValueError('panel_mosaic names must be nonempty strings')
    if not isinstance(panels,Mapping):raise TypeError('panels must map names to content')
    width,height,gap,margin,label_size,label_gap=map(mm,(width,height,gap,margin,label_size,label_gap))
    if not all(math.isfinite(v) for v in (width,height,gap,margin,label_size,label_gap)) or min(width,height,label_size)<=0 or min(gap,margin,label_gap)<0:
        raise ValueError('panel_mosaic needs positive finite sizes and nonnegative gaps/margins')
    names=list(dict.fromkeys(k for row in rows for k in row if k!='.'))
    if not names:raise ValueError('panel_mosaic needs at least one panel')
    if set(panels)!=set(names):raise ValueError(f'panel_mosaic content names must match layout: {names}')
    titles={} if titles is None else dict(titles)
    if titles.keys()-set(names):raise ValueError('panel_mosaic has titles for unknown panels')
    specs={k:(v if isinstance(v,PanelSpec) else PanelSpec(v)) for k,v in panels.items()}
    spans={}
    for name,spec in specs.items():
        if spec.align not in ('start','center','end'):raise ValueError('panel alignment must be start, center or end')
        if spec.aspect is not None and (not math.isfinite(spec.aspect) or spec.aspect<=0 or not callable(spec.content)):raise ValueError('panel aspect requires a factory and a positive finite ratio')
        if any(not math.isfinite(mm(v)) or mm(v)<0 for v in (spec.min_width,spec.min_height)):raise ValueError('panel minimums must be finite and nonnegative')
        cells=[(r,c) for r,row in enumerate(rows) for c,k in enumerate(row) if k==name]
        r0,r1=min(r for r,c in cells),max(r for r,c in cells);c0,c1=min(c for r,c in cells),max(c for r,c in cells)
        if len(cells)!=(r1-r0+1)*(c1-c0+1):raise ValueError(f'panel {name} must occupy a rectangular span')
        spans[name]=(r0,r1,c0,c1)
    headers={}
    for name in names:
        header=[]
        if letters:header.append(i.text(name,size=label_size,weight='bold',markup=False,bounds='ink'))
        if name in titles:header.append(i.text(titles[name],size=label_size*.85,markup=False,bounds='ink'))
        head=i.hstack(header,gap=label_gap) if header else None
        reserve=(head.height+label_gap) if head is not None else 0
        headers[name]=(head,reserve)
    def tracks(n,weights,total,axis):
        automatic=isinstance(weights,str) and weights=='auto'
        if isinstance(weights,str) and not automatic:raise ValueError('track weights must be a sequence or auto')
        weights=[1.]*n if weights is None or automatic else list(weights)
        if len(weights)!=n or any(not math.isfinite(v) or v<=0 for v in weights):raise ValueError('track weights must be finite, positive, and match the layout')
        available=total-2*margin-(n-1)*gap
        if available<=0:raise ValueError('margins and gaps consume the page')
        sizes=[available*v/sum(weights) for v in weights]
        requirements=[]
        for name,spec in specs.items():
            r0,r1,c0,c1=spans[name];a,b=(c0,c1) if axis=='x' else (r0,r1)
            minimum=mm(spec.min_width if axis=='x' else spec.min_height)
            if automatic:
                head,reserve=headers[name]
                minimum=max(minimum, (head.width if head is not None else 0) if axis=='x' else reserve)
                content=spec.content
                if not callable(content) and hasattr(content,'build'):content=content.build()
                if isinstance(content,Diagram) and content.bbox is not None:
                    minimum=max(minimum,content.width if axis=='x' else content.height+reserve)
            if minimum:requirements.append((a,b+1,max(.001,minimum-gap*(b-a))))
        if requirements:sizes=_constrained_tracks(sizes,requirements)
        starts=[margin]
        for size in sizes[:-1]:starts.append(starts[-1]+size+gap)
        return starts,sizes
    xs,ws=tracks(len(rows[0]),column_weights,width,"x");ys,hs=tracks(len(rows),row_weights,height,"y")
    nodes=[];records={}
    for name in names:
        cells=[(r,c) for r,row in enumerate(rows) for c,k in enumerate(row) if k==name]
        r0,r1=min(r for r,c in cells),max(r for r,c in cells)
        c0,c1=min(c for r,c in cells),max(c for r,c in cells)
        if len(cells)!=(r1-r0+1)*(c1-c0+1):raise ValueError(f'panel {name} must occupy a rectangular span')
        x,y=xs[c0],ys[r0];w=sum(ws[c0:c1+1])+gap*(c1-c0);h=sum(hs[r0:r1+1])+gap*(r1-r0)
        head,reserve=headers[name]
        if head is not None and head.width>w:raise DiagramError(f'panel {name} header exceeds its column; shorten the title or enlarge the panel')
        budget=h-reserve
        if budget<=0:raise DiagramError(f'panel {name} has no room below its header')
        spec=specs[name];item=spec.content;aw,ah=w,budget
        for attempt in range(12):
            if spec.aspect is not None:
                aw=min(aw,ah*spec.aspect);ah=aw/spec.aspect
            node=item(aw,ah) if callable(item) else item
            node=node.build() if hasattr(node,'build') else node
            if not isinstance(node,Diagram) or node.bbox is None:raise TypeError(f'panel {name} must produce a nonempty Diagram or Panel')
            b=node.bbox;dw=max(0,b.width-w);dh=max(0,b.height-budget)
            if dw<=1e-6 and dh<=1e-6:break
            if not callable(item):raise DiagramError(f'panel {name} does not fit; provide a factory(width, height) to rebuild it')
            aw-=dw+(.05 if dw else 0);ah-=dh+(.05 if dh else 0)
            if min(aw,ah)<=0:raise DiagramError(f'panel {name} cannot fit at this font/content size')
        else:raise DiagramError(f'panel {name} did not converge; simplify its furniture or enlarge its slot')
        node=node.translated(x+(w-b.width)/2-b.x0,y+reserve+(budget-b.height)*{"start":0,"center":.5,"end":1}[spec.align]-b.y0)
        nodes.append(node)
        if head is not None:nodes.append(head.translated(x-head.bbox.x0,y-head.bbox.y0))
        b=node.bbox
        records[name]={'slot':(x,y,x+w,y+h),'content':(b.x0,b.y0,b.x1,b.y1),'builds':attempt+1,'drawing_size':(aw,ah),'aspect':spec.aspect}
    from ..figure import apply_theme
    return apply_theme(Diagram(children=tuple(nodes),kind='panel-mosaic',envelope_override=Envelope.from_rect(Rect(0,0,width,height)),notes={'panel_mosaic':records}),i.current_theme())
