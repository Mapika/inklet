"""Reproducible figure projects with verified assets and explicit correspondence.

Saved files carry independently versioned schemas: `inklet.figure-project/0.1`,
`inklet.assets/0.1` and `inklet.entities/0.1`. Bundles contain data and choices,
never an executable object serialization. Reopening requires a trusted factory.
Available in 4.3; the same objects remain importable from
`inklet.experimental.project`.
"""
import json
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import warnings

from .assets import Asset, AssetManifest, name as _name
from .identity import EntityMap
from ..editor import LayoutEditor
from ..document.layout_overrides import _targets

__all__ = ['Asset', 'AssetManifest', 'EntityMap', 'ExportDriftWarning', 'FigureProject']
SCHEMA = 'inklet.figure-project/0.1'


class ExportDriftWarning(UserWarning):
    """A reopened project's SVG differs from the export recorded when it was saved.

    The project still opens with its saved choices applied. The recipe, fonts or
    Inklet version changed the rendering; review the figure, then save again to
    record the new export. Pass ``verify_export='strict'`` to raise instead.
    """


class FigureProject:
    """Connect a Composition editor, an asset inventory and entity selection.

    Bind named composition paths through the reserved ``composition`` source.
    Other source IDs are validated against their tables or adapter inventories
    using EntityMap.validate_source(). Selection does not silently restyle artwork;
    targets() returns the explicit IDs for an author's highlight or linked view.
    """

    def __init__(self, name, recipe, *, assets=None, identities=None, selected=(),
                 width=None, height=None, preset=None):
        self.name = _name(name, 'project name')
        self.assets = AssetManifest() if assets is None else assets
        self.identities = EntityMap() if identities is None else identities
        if not isinstance(self.assets, AssetManifest) or not isinstance(self.identities, EntityMap):
            raise TypeError('project needs an AssetManifest and EntityMap')
        from ..selection import _ids
        #: How `open` compared the reconstructed export; None for a new project.
        self.open_report = None
        self.selected = _ids(selected, "entity selection")
        self.identities.targets(self.selected)
        if 'composition' in self.identities.sources:
            paths = _targets(recipe)
            missing = set(self.identities.sources['composition']) - paths.keys()
            if missing:
                raise ValueError(f'unknown composition identity paths: {sorted(missing)}')
        self.editor = LayoutEditor(recipe, width=width, height=height, preset=preset)

    def select(self, source, local_ids):
        """Select through any registered content source; return all linked targets."""
        selected = self.identities.selected(source, local_ids)
        self.selected = selected
        return self.identities.targets(selected)

    def state_for(self, figure):
        """Apply canonical selection to a BrowserFigure built from joined_table()."""
        from ..selection import SelectionState
        if tuple(figure.table.row_ids) != self.identities.entities:
            raise ValueError('linked figure must use the canonical entity table')
        return figure.state(SelectionState.for_table(figure.table, selected=self.selected))

    def select_state(self, figure, state):
        """Transfer a validated linked-view selection back into the project."""
        self.state_for(figure)
        selection, _ = figure.validate_state(state)
        self.identities.targets(selection.selected_ids)
        self.selected = selection.selected_ids
        return self.identities.targets(self.selected)

    def _state(self):
        from .. import __version__
        return dict(schema=SCHEMA, inklet_version=__version__, name=self.name, assets=self.assets.to_dict(),
                    identities=self.identities.to_dict(), selected=list(self.selected),
                    layout=self.editor.overrides(),
                    svg_sha256=hashlib.sha256(self.editor.figure.to_svg().encode()).hexdigest(),
                    editor=dict(width=self.editor.width, height=self.editor.height, preset=self.editor.preset))

    def save(self, directory, *, asset_root):
        """Stage a new portable directory with verified assets and SVG/PDF exports.

        Existing targets are refused. Sources are reverified after copying so a
        file changed during export cannot create a falsely verified bundle.
        """
        paths = self.assets.verify(asset_root)
        destination = Path(directory).absolute()
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix='.inklet-project-', dir=destination.parent))
        try:
            for asset in self.assets.assets:
                target = stage / asset.path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(paths[asset.id], target)
            self.assets.verify(stage)
            metadata = stage / '.inklet'
            metadata.mkdir()
            state = self._state()
            (metadata / 'project.json').write_text(json.dumps(state, indent=2, sort_keys=True)+'\n', encoding='utf-8')
            self.editor.figure.save(metadata / 'figure.svg', metadata / 'figure.pdf')
            if destination.exists():
                raise FileExistsError(destination)
            os.rename(stage, destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        return destination

    @classmethod
    def open(cls, directory, factory, *, verify_export=True):
        """Verify the bundle, then call trusted factory(root) to rebuild its recipe.

        Never import or execute Python stored in the bundle automatically. Asset
        hashes establish consistency, not authorship or trust in supplied code.

        ``verify_export`` compares the reconstructed SVG with the saved digest.
        ``True`` (the default) reopens a differing project and emits an
        `ExportDriftWarning`; ``'strict'`` raises ValueError instead; ``False``
        skips the comparison. Asset hashes are always verified. The outcome is
        recorded in the returned project's ``open_report`` dictionary.
        """
        if verify_export not in (True, False, 'strict'):
            raise ValueError("verify_export must be True, False or 'strict'")
        root = Path(directory).resolve()
        state_path = root / '.inklet' / 'project.json'
        if not state_path.resolve().is_relative_to(root):
            raise ValueError('project metadata lies outside bundle')
        value = json.loads(state_path.read_text(encoding='utf-8'))
        if (not isinstance(value, dict) or set(value) != {
                'schema', 'inklet_version', 'name', 'assets', 'identities', 'selected', 'layout', 'editor', 'svg_sha256'}
                or value['schema'] != SCHEMA):
            raise ValueError('unsupported figure project')
        assets = AssetManifest.from_dict(value['assets'])
        assets.verify(root)
        identities = EntityMap.from_dict(value['identities'])
        identities.targets(value['selected'])
        if not isinstance(value['editor'], dict) or set(value['editor']) != {'width', 'height', 'preset'}:
            raise ValueError('invalid project editor options')
        result = cls(value['name'], factory(root), assets=assets, identities=identities,
                     selected=value['selected'], **value['editor'])
        result.editor.command('load', value['layout'])
        report = dict(verify_export=verify_export, saved_svg_sha256=value['svg_sha256'],
                      saved_inklet_version=value['inklet_version'],
                      svg_sha256=None, export_drift=None)
        if verify_export:
            digest = hashlib.sha256(result.editor.figure.to_svg().encode()).hexdigest()
            report.update(svg_sha256=digest, export_drift=digest != value['svg_sha256'])
            if report['export_drift']:
                message = ('reconstructed figure differs; check recipe, Inklet version and fonts '
                           f"(saved with Inklet {value['inklet_version']})")
                if verify_export == 'strict':
                    raise ValueError(message)
                warnings.warn(message, ExportDriftWarning, stacklevel=2)
        result.open_report = report
        return result

    def revise(self, recipe, *, assets=None, identities=None, missing='error'):
        """Return a new project, preserving valid choices and reporting conflicts.

        Removed entities or changed local bindings require missing='drop'. Even
        unselected remappings are reported. The previous project stays unchanged.
        New assets must be explicitly captured; save() verifies their bytes.
        """
        if missing not in ('error', 'drop'):
            raise ValueError('missing must be error or drop')
        identities = self.identities if identities is None else identities
        report = self.identities.changes(identities)
        if missing == 'error' and (report['removed_entities'] or report['changed_bindings']):
            raise ValueError(f'identity revision requires explicit reconciliation: {report}')
        restored, layout_report = recipe.with_layout_overrides(self.editor.overrides(), missing=missing)
        result = type(self)(self.name, recipe, assets=self.assets if assets is None else assets,
                            identities=identities, selected=tuple(e for e in self.selected if e in identities.entities),
                            width=self.editor.width, height=self.editor.height, preset=self.editor.preset)
        result.editor.command('load', restored.layout_overrides(recipe))
        report['layout'] = layout_report
        report['removed_selection'] = sorted(set(self.selected)-set(result.selected))
        return result, report
