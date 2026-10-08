# FigBench: can a coding agent make the figure right first time?

Status: design, 2026-10-08. Nothing here has been run yet.

## What it measures

inklet claims that a coding agent gets a correct, publication-ready figure
in fewer tries with inklet than with matplotlib, and that inklet's checks
catch the figures that look fine but are wrong. FigBench tests that claim
with the people it is about: agents doing realistic plotting requests that
a researcher would type, graded without trusting either library's own
report.

The headline numbers, per library and per model:

| Metric | Definition |
| --- | --- |
| **Correct at hand-off** | Share of runs where the figure the agent hands back passes every must-pass check. This is the primary metric. |
| **Silent failure** | Share of runs where the agent says it is done but at least one must-pass check fails. This is the failure inklet exists to prevent. |
| **Spec compliance** | Share of runs that meet the stated journal spec: size, font range, embedded fonts, nothing clipped or overlapping, file-size limit. |
| **Effort** | Script runs, tool calls, turns, tokens and wall time to hand-off. |
| **Preference** | Blind pairwise choice between the two libraries' figures for the same run: "which would you submit?" |

## Design principles

1. **Library-neutral grading.** inklet's lint is never used to grade. If it
   were, the benchmark would only measure agreement with inklet's own rules.
   Every check reads the delivered PDF/PNG, the same way for both libraries.
2. **Realistic prompts, hidden traps.** Each task is phrased the way a
   researcher asks ("plot mean reaction time per condition with SEM and the
   individual points, for a Nature single column"). Each task also hides one
   or two pitfalls from the usability runs: replicate rows, two series on
   very different scales, `$...$` units, long category names, journal font
   limits. The prompt never mentions the pitfall.
3. **Equal footing.** Both arms get the same model, prompt (apart from the
   library name), tools, data, budget and time limit. Each library comes with
   what it ships for agents: inklet has `inklet guide`; matplotlib has the
   agent's training and the internet's worth of examples it has absorbed. An
   ablation arm runs inklet without the guide to show how much the guide
   itself contributes.
4. **No teaching to the test.** Tasks are split into a dev set (whose failures
   drive inklet fixes) and a held-out test set that only the frozen headline
   run sees. The test set is committed with a hash before the run, and the
   headline is reported whatever it says.
5. **Everything public.** Tasks, data, checks, judge prompts, harness, raw
   transcripts and figures are published with the results.

## Arms

| Arm | Draws with | Agent is told |
| --- | --- | --- |
| `mpl` | matplotlib (seaborn, pandas, scipy, statsmodels, lifelines allowed) | "Use matplotlib (seaborn is fine)." |
| `inklet` | inklet (numpy/pandas/scipy allowed for computation) | "Use inklet. `inklet guide` prints its agent guide." |
| `inklet-noguide` (ablation) | inklet | "Use inklet." |

A plotly arm is optional later. Journals want static vector files, which is
inklet's wedge, so plotly is not the incumbent there.

Models: Haiku, Sonnet and Opus, all through headless Claude Code. A
non-Claude agent (Codex CLI) is a stretch goal for the published run, so the
claim does not rest on one vendor.

## Tasks

There are 20 tasks in four tiers. Each one is drawn from a figure type that
shows up constantly in papers, and each one carries its trap. They are split
10 dev and 10 test, stratified by tier. Which task lands in which split is
chosen at random with a seed, after the tasks are written.

### Tier 1: everyday charts

1. **Time course with CI:** reporter signal for 3 conditions over 48 h,
   tidy table with 4 replicates per time point. Trap: replicates must be
   averaged with a CI ribbon, not drawn as zigzag lines.
2. **Bars with SEM and points:** 4 conditions × 2 genotypes, replicate rows.
   Trap: a default sum over replicates. Bars must show means.
3. **Regression with equation:** scatter, fitted line, and `y = ax + b` with
   R² on the plot. Trap: `$R^2$` mathtext habit; R² must render as R².
4. **Two overlaid histograms with mean lines:** labelled mean rules. Trap:
   labels jammed against the tallest bar; transparency so both show.
5. **Monthly series:** sales by month name over two years from a CSV. Trap:
   alphabetical month order; date parsing.

### Tier 2: field-specific figures

6. **Volcano plot:** 5000 genes, thresholds, top 10 genes labelled. Traps:
   −log10 transform, labels over threshold lines and each other, subscript in
   `log_{2}` axis title.
7. **Kaplan–Meier:** two arms, censor ticks, number-at-risk table below.
   Trap: step function and censor marks; table aligned to the time axis.
8. **Dose–response:** 4PL fit on log concentration with EC50 marked, plus a
   zero-concentration control. Trap: zero on a log axis.
9. **Expression heatmap:** 30 genes × 12 samples, z-scored, diverging map
   centred at 0, long gene names. Trap: uncentred colour map, unreadable labels.
10. **Forest plot:** 8 studies plus pooled hazard ratio, log scale, reference
    at 1, weights column. Trap: linear axis for ratios.
11. **Climate chart:** monthly temperature (°C) and precipitation (mm). Trap:
    one axis flattens a series; month order; degree sign.
12. **Box + points with significance brackets:** 6 groups, 2 comparisons.
    Trap: brackets clipped or overlapping data.
13. **Ranked horizontal bars:** 15 pathways with long names sorted by score,
    best at the top. Trap: reversed order, clipped labels.

### Tier 3: publication layouts

14. **Nature single-column two-panel figure:** (a) line, (b) bars, 89 mm wide,
    5–7 pt text, PDF. Traps: physical size, font limits, panel letters.
15. **Double-column 2×2 figure:** the same condition has the same colour in
    every panel, with one shared legend. Trap: inconsistent colours.
16. **Small multiples:** 9 sites in a grid with a shared y axis. Trap: crowded
    ticks; axis titles repeated on every panel.
17. **Large scatter:** 200 000 points with a density cue, PDF under 5 MB.
    Trap: a 60 MB vector file.
18. **Annotated time series:** 4 labelled events and 2 shaded periods. Trap:
    event labels overlapping each other or the shading.

### Tier 4: revision

19. **Reviewer comments:** an existing script in the arm's library makes a
    flawed figure. Fix the five listed reviewer points without breaking the
    rest.
20. **Accessibility pass:** make a given figure colour-blind safe and readable
    in greyscale print, without changing the data shown.

## Grading

Each task's `checks.yaml` lists checks. Each check is marked `must` (counts
for correctness) or `should` (counts for quality). Grading has three layers.

### 1. Artifact checks (deterministic, both libraries alike)

These read the delivered PDF with `pdfplumber`/`pypdf` and the PNG with
Pillow:

- the file exists, in the requested format, and opens;
- **page size** within ±1 mm of the requested width (and height limit);
- **font sizes** of every character, against the spec's min/max in points;
- **embedded fonts**: no Type 3 fonts where the journal forbids them (a real
  matplotlib default that journals bounce);
- **text overlap**: character boxes of different words intersecting;
- **clipping**: text or marks beyond the page edge;
- **file size** under the stated limit; vector where vector was asked for.

### 2. Content checks

These are task-specific. Text-level checks come from the PDF text layer:

- tick labels in the right order (months, ranked pathways top to bottom);
- axis titles containing the unit;
- legend entries;
- no literal `$`;
- panel letters a and b each present once.

Quantitative checks go to a **vision judge** as yes/no questions built from
the reference values, for example "the bar for KO + drug ends between 3.7 and
4.5 on the y axis" or "both series show visible month-to-month change".
Judge rules:

- The judge model is different from the agent's model.
- Each question is asked 3 times, and the majority answer counts.
- The judge sees the figure and the question, never the arm.

A human (us) grades a random 10% of runs blind, and the judge's agreement
with the human is published. If agreement falls under 90% on a check, that
check is rewritten until it reaches 90%.

Later: a library-neutral **geometry reader** that calibrates the axes from
tick labels in the PDF and measures bar ends and point positions. That would
turn the main quantitative checks deterministic. It is not required for v1.

### 3. Preference

For each (task, model, repetition), the final figures from `mpl` and `inklet`
go side by side in random order. The judge (and humans, on a subset) answers
"which would you submit to the journal named in the task, and why".

## Protocol

**Sandbox.** Each run gets a fresh temporary directory with:

- the task's data files and its prompt;
- a fresh venv with pinned versions of the arm's library, installed from the
  wheel. There is no inklet source checkout, so the agent can't read the code
  or the tests.

**Agent.** Each run is one invocation of headless Claude Code:
`claude -p "<prompt>" --bare --model <m> --output-format stream-json
--allowedTools "Bash Read Write Edit" --max-budget-usd <cap>`, run in the
sandbox directory under a wall-clock timeout.

- `--bare` keeps the user's own memory, skills, plugins and CLAUDE.md out of
  the run, so an installed inklet skill can't leak into the `mpl` arm. It
  needs `ANTHROPIC_API_KEY`.
- Every arm can view its own PNG output with Read, as a real user's agent
  can.

**Hand-off.** The run ends when the agent stops. Whatever is at the required
output path at that moment is graded. The transcript is parsed for script
runs, tool calls, tokens and the agent's final claim.

**Repetitions.** 3 per (task, arm, model). The order of runs is randomised.

**Budget.** Per-run caps: a dollar amount (`--max-budget-usd`) and 15
minutes. A run that hits a cap is graded on whatever it delivered and flagged.

## Size and cost

- **Full run:** 20 tasks × 3 arms × 3 models × 3 repetitions = 540 agent
  runs, plus judge calls.
- **Headline only** (test set, 2 arms, 3 models): 180 runs.
- **Cost:** a pilot measures the per-run token use before any full run is
  priced. No large run starts without the maintainer's approval of the
  estimate.

## Phases

1. **Build:**
   - the harness;
   - the artifact checks;
   - the judge;
   - 4 tasks with references and checks (one per tier);
   - a dry-run mode that grades hand-written solutions instead of agents, so
     every check is tested against a known-good and a known-bad figure in
     each library before an agent is involved.
2. **Pilot:**
   - 4 tasks × `mpl`/`inklet` × Sonnet × 2 repetitions;
   - calibrate the judge against human grades;
   - measure cost per run;
   - fix harness bugs.
3. **Write the rest:** 16 more tasks, using the same dry-run gate.
4. **Dev run:**
   - the dev set on all arms and models;
   - inklet failures become the next fix batch, as the usability runs did.
5. **Headline:**
   - freeze inklet and the test set (hash committed);
   - run the test set;
   - publish the results page, raw data and transcripts for the 5.0 launch.

## Layout in the repository

```
bench/
  DESIGN.md                 this file
  tasks/NN-slug/
    task.yaml               id, title, field, tier, split, prompt template,
                            data files, deliverables, spec (width_mm,
                            font_pt range, formats, size limit)
    data/                   inputs, generated by make_data.py with a fixed seed
    make_data.py
    reference/              our solutions in both libraries, plus a known-bad
                            figure per library for the dry-run gate
    checks.yaml             must/should checks: artifact, text, judge questions
  harness/
    sandbox.py              venv + data + prompt per run
    run.py                  claude -p invocation, timeout, transcript capture
    transcript.py           script runs, tool calls, tokens, final claim
  grade/
    artifact.py             PDF/PNG checks (pdfplumber, pypdf, Pillow)
    text.py                 PDF text-layer checks
    judge.py                vision judge, majority of 3, cached
    preference.py           blind pairwise
  report/
    build.py                tables and an HTML results page
  results/                  gitignored raw runs; published separately
```

The bench has its own dependencies (`pdfplumber`, `pypdf`, `pyyaml`, plus
matplotlib/seaborn/lifelines for the `mpl` arm's sandbox). They go in a
`bench` extra and never become inklet dependencies.

## Threats to validity, and the answer to each

- **The tasks favour inklet.** Most tasks come from the usability runs, where
  inklet was weak, and from the matplotlib comparison gallery
  (`examples/compare`), where matplotlib's versions are idiomatic. Before any
  run, someone fluent in matplotlib reviews every prompt and reference.
- **The traps favour inklet** (its lint was built for them). These traps are
  what goes wrong in real figures, whichever library draws them. The report
  also gives the trap-free checks (plain correctness and spec) as their own
  score.
- **matplotlib gets no guide.** The ablation arm shows how much the guide
  carries. A "matplotlib + best-practice prompt" arm can be added if
  reviewers ask for it.
- **Judge error.** Human calibration, 3-vote majority, published agreement.
- **Overfitting.** The held-out test set, frozen before the headline run.
- **One vendor's agents.** Three Claude models, with a non-Claude agent as
  the stretch goal.
