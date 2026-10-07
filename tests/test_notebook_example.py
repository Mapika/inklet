"""The quickstart notebook is executed: every code cell has output and none is an error."""
from pathlib import Path

import pytest

nbformat = pytest.importorskip('nbformat')

NOTEBOOK = Path(__file__).resolve().parents[1] / 'examples' / 'notebooks' / 'quickstart.ipynb'


def test_quickstart_notebook_outputs():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    code = [cell for cell in notebook.cells if cell.cell_type == 'code']
    assert code, 'the notebook has no code cells'
    for number, cell in enumerate(code):
        assert cell.outputs, f'code cell {number} has no stored output: {cell.source.splitlines()[0]}'
        errors = [output for output in cell.outputs if output.output_type == 'error']
        assert not errors, f'code cell {number} failed: {errors[0].ename}: {errors[0].evalue}'
