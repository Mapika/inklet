"""Connectors: arrows that touch the shapes they point at.

`link()` declares one, `route()` turns it into geometry once layout has run,
`route_all()` does a figure's worth in one pass. Depends on `inklet.core` alone.
"""

from .link import (
    CLEARANCE, CONNECTOR_KIND, DEFAULT_ARROW_SIZE, DEFAULT_LOOP,
    DEFAULT_SHOULDER, FLAG_COINCIDENT, FLAG_NO_CLEAR_ROUTE, FLAG_OVERLAP,
    FLAG_SEP, FLAG_SHORT, FLAG_SOURCE_MISSED, FLAG_SOURCE_NO_EXTENT,
    FLAG_SOURCE_NO_TRACE, FLAG_TARGET_MISSED, FLAG_TARGET_NO_EXTENT,
    FLAG_TARGET_NO_TRACE, FLAG_ZERO_LENGTH, HEAD_KIND, HEADS, KINDS,
    LABEL_KIND, LABEL_SIDES, LINK_KIND, LOOP_SIDES, ROUTES, Link, LinkError,
    Obstacle, is_degenerate, link, link_ends, link_flags, link_name, route,
    route_all,
)

__all__ = [
    "Link", "LinkError", "Obstacle", "link", "route", "route_all",
    "link_ends", "link_flags", "link_name", "is_degenerate",
    "LINK_KIND", "CONNECTOR_KIND", "HEAD_KIND", "LABEL_KIND", "FLAG_SEP",
    "KINDS", "ROUTES", "HEADS", "LABEL_SIDES", "LOOP_SIDES",
    "DEFAULT_ARROW_SIZE", "DEFAULT_SHOULDER", "DEFAULT_LOOP", "CLEARANCE",
    "FLAG_COINCIDENT", "FLAG_ZERO_LENGTH", "FLAG_OVERLAP", "FLAG_SHORT",
    "FLAG_SOURCE_NO_TRACE", "FLAG_TARGET_NO_TRACE",
    "FLAG_SOURCE_MISSED", "FLAG_TARGET_MISSED",
    "FLAG_SOURCE_NO_EXTENT", "FLAG_TARGET_NO_EXTENT",
    "FLAG_NO_CLEAR_ROUTE",
]
