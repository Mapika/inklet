# Command-line reference

The installed `inklet` command and `python -m inklet` use the same entry point.
Run `inklet --help` or `inklet <command> --help` for the installed version's
arguments.

## Author script contract

A script should define `make_document()` returning a Document, or
`make_figure()` returning a Figure. The loader also accepts a top-level `doc`
or `fig`. A factory may return a CompiledFigure. It looks for these in that
order, preferring `make_document()` over `make_figure()`.

```python
import inklet as i

def make_document():
    doc = i.document(width=100)
    doc.add('message', i.component(i.text, 'Hello, Inklet'))
    return doc
```

The loader executes author code, including module-level code, then calls the
factory. Put direct-run saves under `if __name__ == '__main__':` so loading a
script does not create additional outputs. Sibling imports are supported.

## Build once

```sh
inklet build examples/v25_document.py --output out/review --name document
```

The command compiles the figure and prints the resulting review path. Default
output is `out/review`, with base name `figure`.

| Option | Effect |
|---|---|
| `--output PATH` | Output directory |
| `--name NAME` | Base filename; starts with an alphanumeric character and permits letters, digits, `_`, `-`, `.` |
| `--dpi NUMBER` | Positive preview DPI; otherwise the publication profile's value or 150 |
| `--compare-to PATH` | Previous manifest, or directory containing `<name>-manifest.json` |
| `--no-pdf-preview` | Omit Poppler's PNG rendering; still save the PDF |
| `--png-backend NAME` | `resvg` (default in v3) or `chromium` |
| `--vectors-only` | Write SVG and PDF without an HTML bundle or preview tools |

`--vectors-only` cannot be combined with `--compare-to`. Bundle export embeds
fonts unless the document profile chooses outlined text; there is no CLI
`--text` flag. Set the profile or use the Python export API.

A successful build exits zero even when the figure has diagnostic findings.
Compilation/export failures exit nonzero. To enforce your own diagnostic policy,
inspect `compiled.diagnostics` or the exported JSON in a validation script.

## Watch and preview

```sh
inklet watch examples/v25_document.py --output out/review --name document \
  --watch data.csv --watch assets/ --port 8765
```

The server binds to `127.0.0.1`, with default port 8765. Open the printed URL.
Watch accepts the shared build options above except `--vectors-only`, plus:

| Option | Default | Effect |
|---|---|---|
| `--port NUMBER` | `8765` | Local preview port |
| `--interval SECONDS` | `0.5` | Positive polling interval |
| `--build-timeout SECONDS` | `600` | Maximum duration of one rebuild |
| `--watch PATH` | None | Additional file or directory; repeat for more paths |

Python files under the author script's directory are watched automatically.
Explicit directories also include non-Python files. Hidden paths,
`__pycache__`, `node_modules` and directories named `out` are excluded from
recursive watching. After a successful bundle, Blender scene dependencies in
its manifest are also watched. Other dependencies need `--watch` entries.

Each rebuild runs in a fresh Python process, with a 600-second default build timeout.
The browser displays the last successful bundle if a build fails and shows
the error alongside it. The next successful edit refreshes the preview.
Stop with Ctrl-C.

Without `--compare-to`, successful watch builds compare against the preceding
bundle. Supply a fixed reference to compare every revision against the same
baseline. See [revision review](export-review.md#compare-revisions).

## Check the environment

```sh
inklet doctor
```

Reports Python, Pillow, NumPy, resvg, Blender (path/version), Chrome/Chromium,
Poppler and Fontconfig as JSON.
This command does not validate fonts or figure geometry, and missing optional
tools do not cause a failing exit code. Use [installation](installation.md)
and [troubleshooting](troubleshooting.md) to resolve missing dependencies.
