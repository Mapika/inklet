"""Measure a document, place named cells, route links and resolve paint."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields, is_dataclass, replace
from collections.abc import Mapping
from types import MappingProxyType
import hashlib
import json
import math
import re
import time

from ..core import Diagram, DiagramError, Envelope, Rect, resolve
from ..plot import Panel, PolarPanel
from ..figure import apply_theme
from ..diagnostics import lint
from ..render.paint import resolve_paint
from ..themes import Theme, theme as get_theme
from .spec import BuildSpec, ComponentSpec, PlotSpec, fingerprint, length, themed
from .data import Dataset
from .compiled import CompiledFigure, CompiledState
from .errors import LayoutError
from .layout import LayoutRequest, layout_document, plot_margins as _margins
from .tracks import allocate_tracks as _tracks


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
    align: str = 'center'


class BuildContext:
    def __init__(self, theme, cache, preset=None):
        self.theme, self.cache = theme, cache
        self.preset = preset
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
        # Fixed factories never receive cell dimensions. Reuse their result
        # across measurement passes and page resizes.
        if isinstance(item, ComponentSpec) and not item.responsive:
            width = height = None
        key = (id(item), repr(fingerprint(item)), width, height, repr(self.theme), repr(self.preset))
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
    preset: object = None
    share_plot_margins: bool = False
    _preset_overrides: dict = field(default_factory=dict, repr=False)
    _cells: list = field(default_factory=list, repr=False)
    _links: list = field(default_factory=list, repr=False)
    _letters: dict = field(default_factory=dict, repr=False)
    _cache: dict = field(default_factory=dict, repr=False)
    _render_previous: object = field(default=None, init=False, repr=False)
    _last: object = field(default=None, repr=False)

    def __post_init__(self):
        if type(self.share_plot_margins) is not bool: raise ValueError('share_plot_margins must be a boolean')
        self.width = length(self.width, 'document width')
        if self.height is not None: self.height = length(self.height, 'document height')
        self.margin = length(self.margin, 'margin', zero=True)
        self.gap = length(self.gap, 'gap', zero=True)
        self.row_gap = self.gap if self.row_gap is None else length(self.row_gap,'row gap',zero=True)
        self.theme = get_theme(self.theme) if isinstance(self.theme,str) else self.theme
        if self.publication is not None:
            from .publication import PublicationProfile
            if not isinstance(self.publication, PublicationProfile): raise TypeError('publication must be a PublicationProfile')
        if self.preset is not None:
            from .presets import Preset
            if not isinstance(self.preset, Preset): raise TypeError('preset must be a Preset')
        if not isinstance(self.theme, Theme): raise TypeError('document theme must be a Theme or theme name')
        if isinstance(self.columns,int) and not isinstance(self.columns,bool):
            if self.columns < 1: raise ValueError('document needs at least one column')
            self.columns = (1.,)*self.columns
        else:
            self.columns = tuple(length(v,'column weight') for v in self.columns)
            if not self.columns: raise ValueError('document needs at least one column')

    def add(self, name, item, *, row=None, column=0, rowspan=1, colspan=1,
            min_width=None, min_height=None, align='center'):
        """Place a named cell; align fixed artwork by a compass point.

        Omitted row appends below existing cells. ``align`` accepts ``center``,
        ``n``, ``s``, ``e``, ``w`` and the four corners. It positions artwork
        within its cell without scaling. Plots fill their available data
        regions and retain shared axis alignment.
        """
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*',name):
            raise ValueError('cell names start with a letter and contain letters, digits, underscores or hyphens')
        if any(c.name == name for c in self._cells): raise DiagramError(f'duplicate cell {name!r}')
        if align not in ('center','n','s','e','w','nw','ne','sw','se'):
            raise ValueError('cell align must be center, n, s, e, w, nw, ne, sw or se')
        row = max((c.row+c.rowspan for c in self._cells), default=0) if row is None else row
        for value,label,minimum in [(row,'row',0),(column,'column',0),(rowspan,'rowspan',1),(colspan,'colspan',1)]:
            if not isinstance(value,int) or isinstance(value,bool) or value < minimum:
                raise ValueError(f'{label} must be an integer >= {minimum}')
        if column+colspan > len(self.columns): raise LayoutError(f'cell {name!r} extends beyond the columns')
        for other in self._cells:
            if (row < other.row+other.rowspan and other.row < row+rowspan
                    and column < other.column+other.colspan and other.column < column+colspan):
                raise LayoutError(f'cell {name!r} overlaps {other.name!r}')
        if isinstance(item,Diagram):
            default_w,default_h = item.width,item.height
        else:
            default_w,default_h = 20,15
        cell=Cell(name,item,row,column,rowspan,colspan,
                  length(default_w if min_width is None else min_width,'minimum width'),
                  length(default_h if min_height is None else min_height,'minimum height'),align)
        self._cells.append(cell)
        self._last=None
        return item

    def configure(self, **options):
        """Validate page changes together before applying them."""
        names=('width','height','columns','margin','gap','row_gap','theme','publication','share_plot_margins')
        unknown=set(options).difference(names)
        if unknown: raise TypeError(f'unknown document options: {unknown!r}')
        candidate=Document(**{name:options.get(name,getattr(self,name)) for name in names}, preset=self.preset)
        for name in names: setattr(self,name,getattr(candidate,name))
        if self.preset is not None: self._preset_overrides.update(options)
        self._last=None
        return self

    def use_preset(self, selected, *, format=None, keep_overrides=True, **options):
        """Switch presets and remeasure live content, preserving explicit page options.

        selected is a preset name or Preset value. Explicit options from the
        original preset.document() and subsequent configure() calls survive;
        keep_overrides=False resets those page choices. Content and recorded
        plot styles are always retained. Pass a customized Preset for branding.
        """
        from .presets import Preset, preset
        if isinstance(selected, str): selected = preset(selected, format=format)
        elif format is not None: raise TypeError('format belongs on preset() when passing a Preset')
        if not isinstance(selected, Preset): raise TypeError('selected must be a preset name or Preset')
        overrides = (self._preset_overrides if keep_overrides else {}) | options
        overrides.setdefault('columns', self.columns)
        candidate = selected.document(**overrides)
        for name in ('width','height','columns','margin','gap','row_gap','theme','publication','preset','share_plot_margins'):
            setattr(self, name, getattr(candidate, name))
        self._preset_overrides = candidate._preset_overrides
        self._last = None
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
                       c.min_width, c.min_height, c.align, fingerprint(c.item, trail)) for c in self._cells),
                fingerprint(self._links, trail), self.share_plot_margins)

    def render(self, context, width=None, height=None):
        self.__post_init__()
        content, _, _, page_height, _ = self._layout(
            context, self.width if width is None else width,
            self.height if height is None else height)
        return Diagram(children=(content,), kind='subfigure', envelope_override=
                       Envelope.from_rect(Rect(0, 0, self.width if width is None else width, page_height)))

    def _layout(self, context, width, height):
        request = LayoutRequest(tuple(self._cells), self.columns, self.margin,
                                self.gap, self.row_gap, dict(self._letters),
                                tuple(self._links), self.share_plot_margins)
        return layout_document(request, context, width, height)

    def compile(self):
        """Measure dependencies and return a cached CompiledFigure snapshot."""
        started=time.perf_counter()
        # Revalidate public page dimensions after direct edits.
        self.__post_init__()
        width=length(self.width,'document width')
        height=None if self.height is None else length(self.height,'document height')
        theme=get_theme(self.theme) if isinstance(self.theme,str) else self.theme
        if not self._cells: raise LayoutError('cannot compile an empty document')
        context=BuildContext(theme,self._cache,self.preset)
        signatures=tuple((c.name,c.row,c.column,c.rowspan,c.colspan,c.min_width,c.min_height,c.align,
                          fingerprint(c.item) if isinstance(c.item,(BuildSpec,Diagram,Panel,PolarPanel)) else id(context.build(c.item)))
                         for c in self._cells)
        key=repr((width,height,self.columns,self.margin,self.gap,self.row_gap,theme,signatures,self._links,self._letters,self.publication,self.preset,self.share_plot_margins))
        if self._last is not None and self._last[0]==key and self._last[1].scene.sources_current():
            return self._last[1]
        dependency_seconds=time.perf_counter()-started
        content, boxes, handles, page_height, passes = self._layout(context, width, height)
        layout_seconds=time.perf_counter()-started
        with themed(theme):
            root=Diagram(children=(content,),kind='page',envelope_override=Envelope.from_rect(Rect(0,0,width,page_height)))
            program=resolve_paint(apply_theme(root,theme),stable_ids=True)
            placements=resolve(program.root)
            paint_finished=time.perf_counter()
            from ..render.scene import compile_scene
            scene = compile_scene(program.root, previous=self._render_previous)
            scene_finished=time.perf_counter()
            diagnostics=tuple(lint(program.root,page=program.root.bbox,placements=placements,page_fill=theme.paper,
                                   **({} if self.publication is None else self.publication.checks)))
        diagnostics_seconds=time.perf_counter()-scene_finished
        state = CompiledState(program.root, MappingProxyType(placements), scene, theme.paper)
        fonts = scene.font_manifest()
        from ..assets.provenance import credits
        from .. import __version__
        alignment = {c.name:c.align for c in self._cells}
        metadata=dict(assets=[asdict(p) for p in credits(program.root)],schema_version=2,inklet_version=__version__,width_mm=width,height_mm=page_height,fonts=fonts,
                      cells={name:dict(x=box.x0,y=box.y0,width=box.width,height=box.height,
                                       node_id=program.ids[handles[name].id],align=alignment[name]) for name,box in boxes.items()},
                      datasets=_sources([c.item for c in self._cells]))
        from ..render.resources import rendering_manifest
        metadata['rendering'] = rendering_manifest(program.root)
        if self.publication is not None: metadata['publication']=asdict(self.publication)
        if self.preset is not None:
            metadata['preset'] = self.preset.as_dict()
            metadata['preset']['page_overrides'] = sorted(self._preset_overrides)
        finished=time.perf_counter()
        stats=dict(build_seconds=finished-started,layout_seconds=layout_seconds,
                   paint_seconds=paint_finished-started-layout_seconds,diagnostics_seconds=diagnostics_seconds,
                   dependency_seconds=dependency_seconds,
                   fitting_seconds=layout_seconds-dependency_seconds,
                   metadata_seconds=finished-scene_finished-diagnostics_seconds,
                   render_scene_seconds=scene_finished-paint_finished,
                   render_scene=dict(scene.stats),
                   cache_hits=context.hits,
                   builds=context.misses,layout_passes=passes,node_count=program.node_count)
        result=CompiledFigure(state,MappingProxyType(boxes),diagnostics,
                              MappingProxyType(metadata),MappingProxyType(stats))
        self._last=(key,result)
        self._render_previous=scene
        return result

    def export(self,directory,**kwargs):
        return self.compile().export(directory,**kwargs)

    def save(self,*paths,**kwargs):
        return self.compile().save(*paths,**kwargs)


def document(*, width=180, height=None, columns=1, margin=4, gap=6, row_gap=None, theme='nature', publication=None, share_plot_margins=False):
    """Create a live document; optionally share plot furniture across the grid.

    Shared margins reserve the largest labels/letters on every plot and use
    the tallest data region plus shared furniture for automatic row heights. Equal tracks and
    unspanned plot cells then have equal data areas. Fixed artwork is unchanged;
    unequal track weights, spans or larger cell minima can still vary areas.
    """
    return Document(width,height,columns,margin,gap,row_gap,theme,publication,share_plot_margins=share_plot_margins)


def subfigure(*, width=180, height=None, columns=1, margin=0, gap=6, row_gap=None, share_plot_margins=False):
    """Create a nested grid. Children inherit the enclosing document theme.

    Use the same add/replace/link/letters API as Document. Width and height are
    defaults; a containing cell supplies the available physical dimensions.
    Nested layout shares measurement caches and runs paint and diagnostics only
    once, when the complete document is compiled.
    """
    return Document(width=width, height=height, columns=columns, margin=margin,
                    gap=gap, row_gap=row_gap,share_plot_margins=share_plot_margins)
