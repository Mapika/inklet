The `recipe.yaml` here is a draft for the conda-forge feedstock (rattler-build v1 format), not a built package.

To submit it:

1. Fork [conda-forge/staged-recipes](https://github.com/conda-forge/staged-recipes) and create a branch.
2. Copy this directory to `recipes/inklet/` in the fork, and check the recipe with `rattler-build build --recipe recipes/inklet/recipe.yaml`.
3. Open a pull request titled "Add new recipe: inklet" and complete the checklist; a conda-forge reviewer then merges it and creates the `inklet-feedstock`.
4. Bump `version`, `source.url` and `source.sha256` in the feedstock for each release, from the PyPI sdist.
