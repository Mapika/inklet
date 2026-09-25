"""The layout editor; moved to `inklet.editor` in 4.3.

This path keeps working and re-exports the same objects. New code should
import from `inklet.editor`.
"""
from inklet.editor import (  # noqa: F401
    BaseHTTPRequestHandler,
    Composition,
    ET,
    LayoutEditor,
    Path,
    SCHEMA,
    ThreadingHTTPServer,
    _EDITORS,
    _expression,
    _placement,
    _targets,
    annotations,
    copy,
    document,
    json,
    math,
    parse_qs,
    secrets,
    threading,
    urlsplit,
)
