# Use Inklet with coding agents

Many people now make plots by asking a coding agent for them. Inklet is built
to make that loop reliable. The agent gets instructions that match the
installed version, the chart API follows conventions it already knows, and
every figure says in plain text what is wrong with it.

## Give the agent the guide

```sh
inklet guide          # how to make charts, layouts and checks, in one page
inklet guide --api    # plus every plot method with its arguments
```

The guide ships inside the package, so it always describes the installed
version. Tell your agent to run `inklet guide` before plotting, or install it
as a skill so the agent loads it on its own:

```sh
inklet skill                     # writes .claude/skills/inklet/SKILL.md
inklet skill ~/.claude/skills    # for every project
```

The skill is the same guide with a description that tells the agent when to
use it. Run the command again after upgrading Inklet. For agents that read
an `AGENTS.md` file, add a line such as *"For plots, use inklet; run
`inklet guide` first."*

The documentation site also publishes [`llms.txt`](llms.txt) and
[`llms-full.txt`](llms-full.txt) for agents that read documentation from the web.

## A call the agent already knows

The [one-call chart API](quick-charts.md) follows the table-first convention
of plotly express and seaborn: `i.line(df, x='time', y='signal',
color='group')`. Agents trained on that convention write correct Inklet code
on the first try, and the chart options borrow familiar names: `xlim`,
`xscale='log'`, `title`.

Errors say what to do. A misspelt column lists the columns that exist, and a
mark with a bad argument names the argument.

## Let the figure report its problems

An agent that cannot see the figure needs to be told what is wrong with it.
Inklet measures every label, so it can:

```sh
inklet check figure.py --png preview.png
```

`check` runs the script, prints the layout report, writes a preview and exits
with status 1 when there are errors (`--strict` also fails on warnings). Each
finding names the overlapping or clipped element and the change that fixes it:

```text
inklet lint: 5 errors

ERROR
  OVERLAP         cell-chart/0/1/0/0/4/0 'treated (24 h)' overlaps cell-chart/0/1/0/0/6/0 'treated (48 h)' over 11.47mm^2, 45% of the smaller box (5.77mm x 1.99mm)  -> separate them by at least 2.99mm along the shorter axis
  ...
```

`--json` prints the same findings as structured data, along with the figure's
size in millimetres and the preview path. In Python, `chart.save()` raises a
`LayoutWarning` carrying the report when something needs attention, so an agent
sees problems in the script's output even if it never calls `report()`.

The script can define `chart`, `fig` or `doc` at module level, or a
`make_chart()`, `make_figure()` or `make_document()` function.

## Headless and deterministic

Nothing in Inklet opens a window or waits for input. `chart.show()` writes an
SVG outside a notebook. The same script produces byte-identical SVG on every
run, so an agent can diff outputs to confirm that a change did what it intended.
