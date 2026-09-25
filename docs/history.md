# Development history

!!! note "Moved"

    This list is now part of [development notes](development.md#earlier-releases-and-studies),
    together with engine studies, design notes and release process pages.

These pages retain earlier release notes, prototype decisions and benchmark
results. They stay at their original URLs so existing links and anchors work,
but are excluded from ordinary documentation search. Use the linked current
guides for supported behavior.

| Historical material | Current guide |
| --- | --- |
| [Inklet v2](v2.md) | [The authoring model](concepts.md) |
| [Inklet 2.5](v2.5.md) | [Panel layout](layout.md) |
| [Rendering in v3](v3.md) | [Meshes and images](three-images.md) |
| [4.0 foundations: selection and engine checks](v4-foundations.md) | [Source revisions and identity](data-revisions.md) |
| [Offline browser rendering](browser-rendering.md) | [Native compiled viewer](compiled-viewer.md) |
| [Plot rendering review](plotting-engine.md) | [Shared plotting quality](plot-quality.md) |
| [Research preview: regions and crossings](research-study.md) | [Research preview and availability](research-preview.md) |
| [Controlling label movement during revision](research-revision.md) | [Research preview and availability](research-preview.md) |
| [Proposed 4.0 engine plan](design/v4.md) | [Current roadmap and release gates](roadmap.md) |
| [Browser backend decision: scatter preview](design/browser-backends.md) | [Native compiled viewer](compiled-viewer.md) |
| [The page-grid combinator: measured, and declined](design/page_grid.md) | [Panel layout](layout.md) |

See the [changelog](../CHANGELOG.md) for version history and the
[current roadmap](roadmap.md) for release acceptance.

## Where new documentation belongs

Extend the existing task guide when behavior changes, and put version-by-version
notes in the [changelog](../CHANGELOG.md). Add a tutorial for a distinct workflow
with a runnable result; add an API reference entry for a callable contract.
Examples can demonstrate different datasets without repeating the full setup
or saved-state specification from their canonical guide.

Keep unique benchmark results, acceptance evidence and design decisions in
Development. When a guide is superseded, preserve its URL and anchors, mark it
as historical, and point readers to the current guide. This keeps old research
and issue links useful while ordinary search shows the instructions to use now.
