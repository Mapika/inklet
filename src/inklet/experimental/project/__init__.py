"""Figure projects; moved to `inklet.project` in 4.3.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. Import from `inklet.project` instead; the objects are the same.
"""
from inklet._compat import moved_module as _moved_module
from inklet.project import (  # noqa: F401
    Asset,
    AssetManifest,
    EntityMap,
    ExportDriftWarning,
    FigureProject,
    LayoutEditor,
    SCHEMA,
    _name,
    _targets,
)

__all__ = ['Asset', 'AssetManifest', 'EntityMap', 'FigureProject']

_moved_module(__name__, 'inklet.project')


def __getattr__(name):
    # The `assets` and `identity` submodules load on first use, so importing
    # this package warns once for itself rather than once per submodule. The
    # submodule's own warning would name this frame; reissue it at the caller.
    if name in ('assets', 'identity'):
        import importlib
        import warnings
        from inklet._compat import InkletDeprecationWarning
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', InkletDeprecationWarning)
            module = importlib.import_module(f'{__name__}.{name}')
        warnings.warn(f'{__name__}.{name} is deprecated and will be removed in Inklet 5.0; '
                      f'import from inklet.project.{name} instead.',
                      InkletDeprecationWarning, stacklevel=2)
        return module
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
