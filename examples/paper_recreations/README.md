# Published-figure stress test

Three complete figures from three Nature Portfolio papers, reconstructed using
released numerical data and native Inklet marks. This is a reproduction study,
not original scientific content for the public gallery. Publisher images are
used for visual comparison only; none is embedded in the recreated figures.

| Recipe | Published figure | Workload |
| --- | --- | --- |
| `immune.py` | [Raharinirina et al., Nature, Fig. 4](https://www.nature.com/articles/s41586-024-08477-8/figures/4) | 11 countries, 22 axes, daily lineage frequencies and fitness intervals |
| `sample.py` | [Rapp et al., Nature Chemical Engineering, Fig. 4](https://www.nature.com/articles/s44286-023-00002-4/figures/4) | 15 axes, 4 × 1,352 trajectories, correlations, uncertainty, percentile ranks and colored scatter |
| `quantum.py` | [Denton et al., Nature Communications, Fig. 5](https://www.nature.com/articles/s41467-024-55124-x/figures/5) | Six 200 × 200 log–log response maps, individual normalization and a shared color key |

Run from the repository root with Inklet installed in the active environment:

```sh
uv pip install numpy pandas openpyxl
.venv/bin/python examples/paper_recreations/fetch.py
.venv/bin/python examples/paper_recreations/recreate.py --review-bundle
.venv/bin/python examples/paper_recreations/review.py
```

Open `out/paper-recreations/index.html` for side-by-side comparisons and links to
SVG, PDF, PNG and measurement JSON. `recreate.py --figure sample` rebuilds one
figure; `--dpi` controls the PNG resolution. The six vector maps take about
16 seconds and produce a roughly 13 MB SVG. See [REPORT.md](REPORT.md) for
fidelity limitations and the resulting Inklet improvement priorities.

`sources.json` records exact URLs and SHA-256 digests. The downloader verifies
existing files as well as new downloads. Paper data and reference figures are
attributed to their original authors under each article's
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) notice. Changes include
redrawing, retypesetting, native-cell rendering and the recipe choices documented
in the report. Author repository material is retrieved from the pinned commit
in the manifest; its source files are not executed. The pickle reader accepts
only the specific NumPy storage types and named tuple needed by that dataset.

The numerical work uses NumPy and pandas. All graphical construction and exports
use Inklet; Matplotlib and the publishers' plotting programs are not run.
Quantum palette constants were sampled from the published color key as style
information; the 240,000 scientific values come exclusively from source data.
