"""Measure a document, place named cells, route links and resolve paint."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields, is_dataclass, replace
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
import hashlib
import json
import math
import re
import time

from ..core import Affine, Diagram, DiagramError, Envelope, Rect, resolve
from ..draw.coords import plot_area
from ..figure import Figure, apply_theme
from ..links import link, route_all
from ..diagnostics import lint, format_report
from ..render.paint import resolve_paint
from ..themes import Theme, theme as get_theme
from .spec import BuildSpec, PlotSpec, fingerprint, length, themed
from .data import Dataset


class LayoutError(DiagramError):
    """A document cannot satisfy its declared physical layout constraints."""


@dataclass(frozen=True)
class Cell:
    name: str
    item: object
    row: int
    column: int
    rowspan: int = 1
    colspan: int = 1
    min_width: float = 20
    min_height: float = 15


class BuildContext:
    def __init__(self, theme, cache):
        self.theme, self.cache = theme, cache
        self.active = []
        self.hits = self.misses = 0

    def build(self, item, width=None, height=None):
        if isinstance(item, Diagram):
            return item
        if not isinstance(item, BuildSpec):
            # Live legacy Panels are accepted at their authored dimensions.
            if hasattr(item, 'build'):
                result = item.build()
                if isinstance(result, Diagram):
                    return result
            raise TypeError('document cells need a Diagram, Panel, PlotSpec or ComponentSpec')
        if id(item) in self.active:
            raise DiagramError('cyclic document dependency')
        key = (id(item), repr(fingerprint(item)), width, height, repr(self.theme))
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.active.append(id(item))
        try:
            with themed(self.theme):
                node = item.render(self, width, height)
        finally:
            self.active.pop()
        if not isinstance(node, Diagram) or node.bbox is None:
            raise DiagramError('document component has no measurable drawing')
        self.misses += 1
        self.cache[key] = node
        # Bound retained intermediate layouts in a long-running preview.
        while len(self.cache) > 512:
            del self.cache[next(iter(self.cache))]
        return node


def _tracks(count, weights, constraints, available, gap, axis):
    """Solve contiguous span minima, then fit weighted tracks to the page.

    Longest paths between prefix sums give an exact feasibility bound. Dykstra
    projections find the closest feasible allocation to the requested weights,
    including overlapping spans whose minimum widths share the middle track.
    """
    spans={}
    for start,span,required,_ in constraints:
        spans[start,span]=max(spans.get((start,span),0),required-gap*(span-1))
    prefix=[0.]*(count+1)
    for end in range(1,count+1):
        prefix[end]=max([prefix[end-1]]+[prefix[start]+required
                         for (start,span),required in spans.items() if start+span==end])
    minimum=prefix[-1]+gap*(count-1)
    if available is not None and minimum>available+1e-6:
        raise LayoutError(f'{axis} requires at least {minimum:.2f} mm; only {available:.2f} mm is available '
                          f'for cells {", ".join(c[3] for c in constraints)}. Increase the page size or reduce cell minima.')
    total=prefix[-1] if available is None else available-gap*(count-1)
    tracks=[total*w/sum(weights) for w in weights]
    sets=[(tuple(range(count)),total,True)]
    sets.extend(((index,),0.,False) for index in range(count))
    sets.extend((tuple(range(start,start+span)),required,False) for (start,span),required in spans.items())
    corrections=[0.]*len(sets)
    for _ in range(10000):
        before=tracks[:]
        for index,(indices,required,equality) in enumerate(sets):
            correction=corrections[index]
            current=sum(tracks[j]+correction for j in indices)
            adjustment=(required-current)/len(indices)
            if not equality: adjustment=max(0.,adjustment)
            for j in indices: tracks[j]+=correction+adjustment
            corrections[index]=-adjustment
        if max(abs(a-b) for a,b in zip(before,tracks))<1e-8:
            if abs(sum(tracks)-total)<1e-6 and min(tracks)>=-1e-6:
                return [max(0.,v) for v in tracks]
    raise LayoutError(f'{axis} constraints did not converge; simplify overlapping spans')


def _margins(node):
    area, box = plot_area(node), node.bbox
    if area is None:
        return (0.,0.,0.,0.)
    return (max(0.,area.x0-box.x0), max(0.,box.x1-area.x1),
            max(0.,area.y0-box.y0), max(0.,box.y1-area.y1))


def _sources(items):
    tables, seen = {}, set()
    def canonical(value):
        if isinstance(value,float) and not math.isfinite(value):
            return {'nonfinite_number':str(value)}
        if isinstance(value,Mapping): return {k:canonical(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)): return [canonical(v) for v in value]
        return value
    def visit(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, Dataset):
            payload = json.dumps(canonical(value.columns), sort_keys=True, default=str, allow_nan=False).encode()
            tables[id(value)] = dict(name=value.name, revision=value.revision, units=dict(value.units),
                                     rows=len(next(iter(value.columns.values()))),
                                     data_sha256=hashlib.sha256(payload).hexdigest(),
                                     source=asdict(value.source) if value.source else None)
        elif isinstance(value, Document):
            # Traverse retained authoring objects directly. A temporary list can
            # reuse an earlier sibling's Python ID and be skipped by `seen`.
            for cell in value._cells: visit(cell.item)
        elif isinstance(value, Mapping):
            for v in value.values(): visit(v)
        elif isinstance(value, (list,tuple)):
            for v in value: visit(v)
        elif is_dataclass(value) and not isinstance(value, (Diagram,Theme)):
            for f in fields(value): visit(getattr(value,f.name))
    visit(items)
    return list(tables.values())


@dataclass(frozen=True)
class CompiledFigure:
    """A resolved snapshot; later authoring changes cannot alter its exports."""
    _figure: Figure = field(repr=False)
    cells: Mapping
    diagnostics: tuple
    metadata: Mapping
    stats: Mapping

    @property
    def root(self):
        return self._figure.build()[0]

    def build(self):
        return self._figure.build()

    def lint(self, **kwargs):
        if not kwargs: return list(self.diagnostics)
        profile=self.metadata.get('publication',{})
        defaults={k:profile[k] for k in ('min_font_pt','min_stroke_mm','min_dpi') if k in profile}
        return self._figure.lint(**(defaults | kwargs))

    def report(self, **kwargs):
        return format_report(self.lint(**kwargs))

    def to_svg(self, *, text=None, **kwargs):
        if text is None: text=self.metadata.get('publication',{}).get('text','embed')
        return self._figure.to_svg(text=text, **kwargs)

    def to_pdf(self, *, text=None, **kwargs):
        if text is None: text=self.metadata.get('publication',{}).get('text','embed')
        return self._figure.to_pdf(text=text, **kwargs)

    def save(self, *paths, **kwargs):
        kwargs.setdefault('text', self.metadata.get('publication',{}).get('text','embed'))
        return self._figure.save(*paths, **kwargs)

    def export(self, directory, **kwargs):
        from ..render.bundle import export_bundle
        profile=self.metadata.get('publication')
        if profile:
            kwargs.setdefault('dpi',profile['dpi'])
            kwargs.setdefault('text',profile['text'])
        return export_bundle(self, directory, **kwargs)


@dataclass(eq=False)
class Document(BuildSpec):
    """A physical page containing named, live figure definitions.

    `columns` is a count or positive track weights. Cells can span tracks.
    Plot areas resize to their cells; typography is rebuilt at its actual size.
    Existing Diagram and Panel inputs retain their authored dimensions.
    """
    width: float = 180
    height: float | None = None
    columns: object = 1
    margin: float = 4
    gap: float = 6
    row_gap: float | None = None
    theme: object = 'nature'
    publication: object = None
    _cells: list = field(default_factory=list, repr=False)
    _links: list = field(default_factory=list, repr=False)
    _letters: dict = field(default_factory=dict, repr=False)
    _cache: dict = field(default_factory=dict, repr=False)
    _last: object = field(default=None, repr=False)

    def __post_init__(self):
        self.width = length(self.width, 'document width')
        if self.height is not None: self.height = length(self.height, 'document height')
        self.margin = length(self.margin, 'margin', zero=True)
        self.gap = length(self.gap, 'gap', zero=True)
        self.row_gap = self.gap if self.row_gap is None else length(self.row_gap,'row gap',zero=True)
        self.theme = get_theme(self.theme) if isinstance(self.theme,str) else self.theme
        if self.publication is not None:
            from .publication import PublicationProfile
            if not isinstance(self.publication, PublicationProfile): raise TypeError('publication must be a PublicationProfile')
        if not isinstance(self.theme, Theme): raise TypeError('document theme must be a Theme or theme name')
        if isinstance(self.columns,int) and not isinstance(self.columns,bool):
            if self.columns < 1: raise ValueError('document needs at least one column')
            self.columns = (1.,)*self.columns
        else:
            self.columns = tuple(length(v,'column weight') for v in self.columns)
            if not self.columns: raise ValueError('document needs at least one column')

    def add(self, name, item, *, row=None, column=0, rowspan=1, colspan=1,
            min_width=None, min_height=None):
        """Place a named cell. Omitted row appends below existing cells."""
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',name):
            raise ValueError('cell names start with a letter and contain letters, digits, underscores or hyphens')
        if any(c.name == name for c in self._cells): raise DiagramError(f'duplicate cell {name!r}')
        row = max((c.row+c.rowspan for c in self._cells), default=0) if row is None else row
        for value,label,minimum in [(row,'row',0),(column,'column',0),(rowspan,'rowspan',1),(colspan,'colspan',1)]:
            if not isinstance(value,int) or isinstance(value,bool) or value < minimum:
                raise ValueError(f'{label} must be an integer >= {minimum}')
        if column+colspan > len(self.columns): raise LayoutError(f'cell {name!r} extends beyond the columns')
        occupied = {(r,c) for r in range(row,row+rowspan) for c in range(column,column+colspan)}
        for other in self._cells:
            if occupied.intersection((r,c) for r in range(other.row,other.row+other.rowspan)
                                     for c in range(other.column,other.column+other.colspan)):
                raise LayoutError(f'cell {name!r} overlaps {other.name!r}')
        if isinstance(item,Diagram):
            default_w,default_h = item.width,item.height
        else:
            default_w,default_h = 20,15
        cell=Cell(name,item,row,column,rowspan,colspan,
                  length(default_w if min_width is None else min_width,'minimum width'),
                  length(default_h if min_height is None else min_height,'minimum height'))
        self._cells.append(cell)
        self._last=None
        return item

    def configure(self, **options):
        """Validate page changes together before applying them."""
        names=('width','height','columns','margin','gap','row_gap','theme','publication')
        unknown=set(options).difference(names)
        if unknown: raise TypeError(f'unknown document options: {unknown!r}')
        candidate=Document(**{name:options.get(name,getattr(self,name)) for name in names})
        for name in names: setattr(self,name,getattr(candidate,name))
        self._last=None
        return self

    def replace(self, name, item):
        """Replace a cell definition while retaining its layout constraints."""
        for index, cell in enumerate(self._cells):
            if cell.name==name:
                self._cells[index]=replace(cell,item=item)
                self._last=None
                return item
        raise KeyError(name)

    def link(self, source, target, **kwargs):
        """Connect named cells, optionally `cell:anchor`, after layout."""
        self._links.append((source,target,dict(kwargs)))
        self._last=None
        return self

    def __getitem__(self, name):
        """Return a named live child for subsequent edits."""
        for cell in self._cells:
            if cell.name == name: return cell.item
        raise KeyError(name)

    def letters(self, *, start='a', **options):
        """Measure panel letters with the cells, reserving room before placement."""
        self._letters = dict(start=start, **options)
        return self

    def signature(self, trail=()):
        return ('subfigure', self.width, self.height, self.columns, self.margin,
                self.gap, self.row_gap, fingerprint(self._letters, trail),
                tuple((c.name, c.row, c.column, c.rowspan, c.colspan,
                       c.min_width, c.min_height, fingerprint(c.item, trail)) for c in self._cells),
                fingerprint(self._links, trail))

    def render(self, context, width=None, height=None):
        self.__post_init__()
        content, _, _, page_height, _ = self._layout(
            context, self.width if width is None else width,
            self.height if height is None else height)
        return Diagram(children=(content,), kind='subfigure', envelope_override=
                       Envelope.from_rect(Rect(0, 0, self.width if width is None else width, page_height)))

    def _layout(self, context, width, height):
        if not self._cells: raise LayoutError('cannot compile an empty document')
        theme = context.theme
        def decorate(node, cell):
            if not self._letters: return node
            from ..draw.annotate import letters
            options = dict(self._letters)
            start = chr(ord(options.pop('start')) + self._cells.index(cell))
            with themed(theme):
                tagged = letters([node], start=start, **options)[0]
            for name,point in node.anchors.items(): tagged.anchor(name,node.transform.apply(point))
            return tagged
        rows=max(c.row+c.rowspan for c in self._cells)
        widths=_tracks(len(self.columns),self.columns,
                       [(c.column,c.colspan,c.min_width,c.name) for c in self._cells],
                       width-2*self.margin,self.gap,'width')
        # Auto-height preserves authored data-region heights plus measured furniture.
        natural_heights = {}
        if height is None:
            for c in self._cells:
                cell_width = sum(widths[c.column:c.column+c.colspan])+self.gap*(c.colspan-1)
                natural = context.build(c.item, cell_width,
                                        c.item.height if isinstance(c.item, PlotSpec) else None)
                natural_heights[c.name] = decorate(natural, c).height
        heights=_tracks(rows,(1.,)*rows,
                        [(c.row,c.rowspan,max(c.min_height, natural_heights.get(c.name,0)),c.name)
                         for c in self._cells],
                        None if height is None else height-2*self.margin,self.row_gap,'height')
        boxes={c.name:Rect(self.margin+sum(widths[:c.column])+self.gap*c.column,
                           self.margin+sum(heights[:c.row])+self.row_gap*c.row,
                           self.margin+sum(widths[:c.column+c.colspan])+self.gap*(c.column+c.colspan-1),
                           self.margin+sum(heights[:c.row+c.rowspan])+self.row_gap*(c.row+c.rowspan-1))
               for c in self._cells}
        margins={c.name:(0.,0.,0.,0.) for c in self._cells}
        nodes={}
        # Tick selection depends on available width, so measure to a stable fit.
        for iteration in range(24):
            for c in self._cells:
                box=boxes[c.name];left,right,top,bottom=margins[c.name]
                if isinstance(c.item,PlotSpec):
                    pw,ph=box.width-left-right,box.height-top-bottom
                    if pw < 5 or ph < 5:
                        raise LayoutError(f'cell {c.name!r} leaves only {pw:.2f} × {ph:.2f} mm for data after labels. Increase its size.')
                    nodes[c.name]=context.build(c.item,round(pw,6),round(ph,6))
                else:
                    pw,ph=box.width-left-right,box.height-top-bottom
                    if pw <= 0 or ph <= 0: raise LayoutError(f'cell {c.name!r} has no space after panel letters')
                    nodes[c.name]=context.build(c.item,pw,ph)
            undecorated={name:node.bbox for name,node in nodes.items()}
            nodes={c.name:decorate(nodes[c.name], c) for c in self._cells}
            measured={c.name:_margins(nodes[c.name]) for c in self._cells}
            if self._letters:
                for c in self._cells:
                    if isinstance(c.item,PlotSpec): continue
                    a,b=undecorated[c.name],nodes[c.name].bbox
                    measured[c.name]=tuple(max(0.,v,old) for v,old in zip(
                        (a.x0-b.x0,b.x1-a.x1,a.y0-b.y0,b.y1-a.y1),margins[c.name]))
            # Share plot margins among unspanned cells in each column/row.
            for c in self._cells:
                if not isinstance(c.item,PlotSpec): continue
                m=list(measured[c.name])
                for other in self._cells:
                    if not isinstance(other.item,PlotSpec): continue
                    n=measured[other.name]
                    if c.column==other.column and c.colspan==other.colspan:
                        m[0],m[1]=max(m[0],n[0]),max(m[1],n[1])
                    if c.row==other.row and c.rowspan==other.rowspan:
                        m[2],m[3]=max(m[2],n[2]),max(m[3],n[3])
                # Monotonic margins prevent tick-thinning oscillations.
                measured[c.name]=tuple(max(a,b) for a,b in zip(m,margins[c.name]))
            if all(max(abs(a-b) for a,b in zip(measured[n],margins[n]))<.005 for n in margins): break
            margins=measured
        else:
            raise LayoutError('plot furniture did not settle after 24 measurement passes')
        placed=[];handles={}
        for c in self._cells:
            node,box=nodes[c.name].copy(),boxes[c.name]
            actual=node.bbox
            if actual.width > box.width+.02 or actual.height > box.height+.02:
                raise LayoutError(f'cell {c.name!r} contains {actual.width:.2f} × {actual.height:.2f} mm '
                                  f'but has {box.width:.2f} × {box.height:.2f} mm. Increase its cell size.')
            if isinstance(c.item,PlotSpec):
                area=plot_area(node);left,_,top,_=margins[c.name]
                dx,dy=box.x0+left-area.x0,box.y0+top-area.y0
            else:
                dx,dy=box.center.x-actual.center.x,box.center.y-actual.center.y
            handles[c.name]=node
            # Always wrap: at zero offset translated() returns the original
            # node, whose semantic kind (e.g. abutting artwork) must survive.
            placed.append(Diagram(children=(node,),transform=Affine.translation(dx,dy),
                                  kind='document-cell',name=c.name).carry_notes(node))
        with themed(theme):
            content=Diagram(children=tuple(placed),kind='document-content')
            if self._links:
                def endpoint(value):
                    if not isinstance(value,str): raise TypeError('document link endpoints must be cell or cell:anchor strings')
                    name,sep,anchor=value.partition(':')
                    if name not in handles: raise DiagramError(f'unknown link cell {name!r}')
                    return handles[name].at(anchor) if sep else handles[name]
                # Figure.link supplies theme-aware labels, plates and arrow defaults.
                builder=Figure(theme=theme)
                for a,b,kw in self._links: builder.link(endpoint(a),endpoint(b),**kw)
                connectors=route_all(builder._links,resolve(content))
                content=Diagram(children=(content,connectors),kind='document-content')
            page_height=height if height is not None else 2*self.margin+sum(heights)+self.row_gap*(rows-1)
        return content, boxes, handles, page_height, iteration+1

    def compile(self):
        """Measure dependencies and return a cached CompiledFigure snapshot."""
        started=time.perf_counter()
        # Revalidate public page dimensions after direct edits.
        self.__post_init__()
        width=length(self.width,'document width')
        height=None if self.height is None else length(self.height,'document height')
        theme=get_theme(self.theme) if isinstance(self.theme,str) else self.theme
        if not self._cells: raise LayoutError('cannot compile an empty document')
        context=BuildContext(theme,self._cache)
        signatures=tuple((c.name,c.row,c.column,c.rowspan,c.colspan,c.min_width,c.min_height,
                          fingerprint(c.item) if isinstance(c.item,(BuildSpec,Diagram)) else id(context.build(c.item)))
                         for c in self._cells)
        key=repr((width,height,self.columns,self.margin,self.gap,self.row_gap,theme,signatures,self._links,self._letters,self.publication))
        if self._last is not None and self._last[0]==key: return self._last[1]
        content, boxes, handles, page_height, passes = self._layout(context, width, height)
        layout_seconds=time.perf_counter()-started
        with themed(theme):
            root=Diagram(children=(content,),kind='page',envelope_override=Envelope.from_rect(Rect(0,0,width,page_height)))
            program=resolve_paint(apply_theme(root,theme),stable_ids=True)
            placements=resolve(program.root)
            paint_finished=time.perf_counter()
            diagnostics=tuple(lint(program.root,page=program.root.bbox,placements=placements,page_fill=theme.paper,
                                   **({} if self.publication is None else self.publication.checks)))
        diagnostics_seconds=time.perf_counter()-paint_finished
        figure=Figure(width=width,height=page_height,margin=0,theme=theme)
        figure._built=(program.root,placements)
        from ..core.prims import TextPrim
        font_paths=set()
        for placement in placements.values():
            prim=placement.diagram.prim
            if isinstance(prim,TextPrim):
                if prim.font_path: font_paths.add(prim.font_path)
                for line in prim.lines:
                    for run in line.runs:
                        if run.font_path: font_paths.add(run.font_path)
        fonts=[dict(file=Path(path).name,sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
               for path in sorted(font_paths)]
        from ..assets.provenance import credits
        from .. import __version__
        metadata=dict(assets=[asdict(p) for p in credits(program.root)],schema_version=2,inklet_version=__version__,width_mm=width,height_mm=page_height,fonts=fonts,
                      cells={name:dict(x=box.x0,y=box.y0,width=box.width,height=box.height,
                                       node_id=program.ids[handles[name].id]) for name,box in boxes.items()},
                      datasets=_sources([c.item for c in self._cells]))
        if self.publication is not None: metadata['publication']=asdict(self.publication)
        stats=dict(build_seconds=time.perf_counter()-started,layout_seconds=layout_seconds,
                   paint_seconds=paint_finished-started-layout_seconds,diagnostics_seconds=diagnostics_seconds,
                   cache_hits=context.hits,
                   builds=context.misses,layout_passes=passes,node_count=program.node_count)
        result=CompiledFigure(figure,MappingProxyType(boxes),diagnostics,
                              MappingProxyType(metadata),MappingProxyType(stats))
        self._last=(key,result)
        return result

    def export(self,directory,**kwargs):
        return self.compile().export(directory,**kwargs)

    def save(self,*paths,**kwargs):
        return self.compile().save(*paths,**kwargs)


def document(*, width=180, height=None, columns=1, margin=4, gap=6, row_gap=None, theme='nature', publication=None):
    """Create a live scientific document with a constrained physical page layout."""
    return Document(width,height,columns,margin,gap,row_gap,theme,publication)


def subfigure(*, width=180, height=None, columns=1, margin=0, gap=6, row_gap=None):
    """Create a nested grid. Children inherit the enclosing document theme.

    Use the same add/replace/link/letters API as Document. Width and height are
    defaults; a containing cell supplies the available physical dimensions.
    Nested layout shares measurement caches and runs paint and diagnostics only
    once, when the complete document is compiled.
    """
    return Document(width=width, height=height, columns=columns, margin=margin,
                    gap=gap, row_gap=row_gap)
