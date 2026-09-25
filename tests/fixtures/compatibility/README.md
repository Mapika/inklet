# Released compatibility fixtures

These files were written using isolated installations of the published wheels,
not the current checkout. `provenance.json` records wheel URLs, archive hashes,
writer versions and hashes for the captured files and their frozen recipe.

- `api-3.1.json`: 204 exported names and 450 callable signatures from 3.1.0.
  Private constructor storage fields are recorded but excluded from the public
  compatibility check. Default values and type annotations are not compared.
- `api-4.2.json`: the 4.2.0 wheel (all extras, Python 3.12.3). Keys are
  namespaced `module:Name` / `module:Class.method`: 220 top-level `__all__`
  names plus 142 public names defined in the 33 public `inklet.experimental`
  modules (987 callable signatures). Private modules such as
  `_table_adapters` are not recorded.
- `dev16-project/`: a complete two-entity project written by 4.0.0.dev16.
- `layout.json` and `selection.json`: saved placement and a selected hidden row,
  also written by dev16.
- `recipe.py`: the trusted reconstruction recipe supplied by the test. Loading a
  bundle never imports this file automatically.

The RC1 wheel reopened the dev16 project with strict SVG hash verification.
Release CI uses the reviewed fonts; other fonts or renderers can legitimately
change SVG bytes. Do not silently disable that verification to pass a candidate.

Keep these historical inputs unchanged. New formats should add appropriately
sourced fixtures rather than replacing old files with current-version output.
An API inventory can be recreated by running
`tools/check_compatibility.py --capture PATH` with the interpreter of an
isolated released-wheel installation (the 3.1 file predates namespaced keys);
`recipe.write()` captures the project and saved choices in a fresh directory.
Neither the tests nor the release checker regenerate fixtures.
