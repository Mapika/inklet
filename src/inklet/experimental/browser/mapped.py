"""Bridge source-native drawing, image and field views to shared entity IDs."""
from dataclasses import dataclass
from .drawings import DrawingView
from .images import LabelImageView
from .fields import MeshFieldView
from .grid import GridFieldView


@dataclass(frozen=True)
class MappedView:
    """Keep source geometry/measurements while exposing canonical picking IDs.

    Plot views use the joined table directly. This adapter supports drawing,
    calibrated image and mesh/grid field views; their source limits still apply.
    """
    source: str
    table: object
    view: object
    identities: object

    def __post_init__(self):
        if type(self.view) not in (DrawingView, LabelImageView, MeshFieldView, GridFieldView):
            raise ValueError('mapped views support drawings, images and mesh/grid fields')
        self.identities.validate_source(self.source, self.table.row_ids)
        if hasattr(self.view, 'validate_table'):
            self.view.validate_table(self.table)

    @property
    def name(self):
        return self.view.name

    def validate_table(self, table):
        expected = self.identities.joined_table(table.name, {self.source: self.table})
        if table.row_ids != expected.row_ids:
            raise ValueError('mapped view requires the canonical entity table')
        for column, values in expected.columns.items():
            if column not in table.columns or table.columns[column] != values:
                raise ValueError(f'mapped view source data mismatch: {column}')

    def legend(self):
        if isinstance(self.view, (MeshFieldView, GridFieldView)):
            view = self.view
            label = ("Corner mean" if view.cells else "Contour level" if view.contours else "") if isinstance(view, GridFieldView) else "Scalar"
            return view.legend(), f"{label} / {view.field.scalar_unit}" if label else ""
        return [], ""

    def layer(self, table, bounds):
        self.validate_table(table)
        layer = self.view.layer(self.table, bounds)
        bindings = self.identities.sources[self.source]
        for mark in layer['marks']:
            original = list(mark['ids'])
            mark['ids'] = [bindings[local] for local in original]
            if original:
                mark['source_ids'] = original
        for key in ('x', 'y', 'value'):
            if layer.get(key) in self.table.columns:
                layer[key] = f'{self.source}__{layer[key]}'
        if 'drawing' in layer:
            layer['drawing']['omitted_ids'] = sorted({bindings[key] for key in layer['drawing']['omitted_ids']})
        layer['correspondence'] = dict(source=self.source, data_digest=self.table.digest, bindings=dict(bindings))
        return layer
