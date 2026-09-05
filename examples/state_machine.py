"""A job's state machine: a retry that loops, and two states that argue.

The three things a flow chart needs that a pipeline does not. `poll` leaves
`running` and comes straight back to it, `pause` and `resume` join the same
two states in opposite directions, and neither takes part in deciding where
the states go -- `inklet.graph` lays out the simple graph underneath and draws
the rest as arcs and bows around it.
"""

import inklet

inklet.use_theme("nature")

STATES = {
    "queued":  "queued",
    "running": "running",
    "paused":  "paused",
    "failed":  "failed",
    "done":    "done",
}

# A mapping edge carries its label, and anything else the link takes. Leaving
# `loop` out lets the graph pick the emptiest side of the box; it is named here
# because the side that is empty when the arc is drawn is the one the retry
# label wants later, and west is the side that stays empty.
EDGES = [
    {"source": "queued", "target": "running", "label": "start"},
    {"source": "running", "target": "running", "label": "poll", "loop": "w"},
    {"source": "running", "target": "paused", "label": "pause"},
    {"source": "paused", "target": "running", "label": "resume"},
    {"source": "running", "target": "failed", "label": "error"},
    # `retry` is the one edge that runs against the flow. Left to itself the
    # router climbs the corridor between `running` and `failed` and crosses
    # `error` on the way; a waypoint sends it straight up out of `failed`
    # instead, into the empty right margin. Written against the node rather
    # than in millimetres, so it is still the right route if `failed` moves.
    {"source": "failed", "target": "queued", "label": "retry",
     "route": "orthogonal", "waypoints": [("failed", "n")]},
    {"source": "running", "target": "done", "label": "finish"},
]

states = {key: inklet.box(text, width=18) for key, text in STATES.items()}

machine = inklet.graph(states, EDGES, direction="down", rank_gap=18, gap=8, lane=5)

fig = inklet.figure(width=inklet.COLUMN_SINGLE, theme="nature")
machine.add_to(fig)

print("%d states, %d transitions, %.1f x %.1f mm"
      % (len(states), len(EDGES), machine.width, machine.height))
print(fig.report())
fig.save("examples/state_machine.svg")
