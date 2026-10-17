# Module directory conventions

This directory contains one self-contained folder per functional module.

- `student/`: student report scripts, runner, docs, notebooks and snapshots.
- `teacher/`: teacher report scripts, runners, docs and retired experiments.
- Future modules: add `modules/<module-name>/README.md`, `scripts/`, a clearly named runner, tests, and module-specific operational notes.

Keep cross-module utilities in `../shared/`. Keep runtime secrets outside Git, and generated reports in `/home/prashant/exports/` rather than beside source files. Update `../docs/VPS-PATHS.md` whenever a canonical path changes.
