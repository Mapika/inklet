"""Immediate connectors for diagrams whose placement is already known."""
from __future__ import annotations

from ..core import Diagram, resolve
from .link import link, route


def connect(source: Diagram, target: Diagram, *, within: Diagram | None = None,
            **kwargs) -> Diagram:
    """Connect two placed shapes, clipping the ends to their actual boundaries.

    Accepts the same options as :func:`inklet.link`, including ``offset`` for
    bowed/opposing edges, ``standoff``, ``arrow_size`` and stroke styling.
    Returns only the connector, in the supplied scene's coordinates; add it
    beneath the nodes. No centering or extra placement is performed.

    Omit ``within`` for two independently placed Diagrams. For nodes nested
    under transformed groups, supply their containing scene so those parent
    transforms are resolved. Recompute after moving a node; use ``Figure.link``
    when placement will be decided later. Obstacle avoidance still belongs to
    ``route_all``/``Figure.link``.
    """
    if not isinstance(source, Diagram) or not isinstance(target, Diagram):
        raise TypeError('connect endpoints must be Diagrams')
    if within is None:
        within = Diagram(children=(source,) if source.id == target.id else (source, target))
    if not isinstance(within, Diagram):
        raise TypeError('connect within must be a Diagram')
    placements = resolve(within)
    if source.id not in placements or target.id not in placements:
        raise ValueError('connect endpoints must both belong to within')
    return route(link(source, target, **kwargs), placements)
