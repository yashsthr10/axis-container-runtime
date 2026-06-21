# Documentation Changelog

Tracks important updates to repository documentation.

## 2026-06-21

- Replaced generic documentation templates with Axis-specific docs.
- Documented the Python CLI and C++ runtime subprocess boundary.
- Added current CLI behavior for `run`, `ps`, `stop`, `inspect`, `logs`, and `clean`.
- Added current `Axisfile` syntax, including `RESTART always` and `VOLUME source:destination`.
- Documented `.axis` state files, runtime JSON, logs, inspect output, restart behavior, networking, and bind mounts.
- Added project-specific architecture decisions, patterns, structure, dependencies, examples, and rules.
- Folded production-hardening notes into existing architecture, specs, and workflow docs instead of keeping a separate productionization page.
- Documented lifecycle state, resource ownership, stats, reconcile, failpoints, cgroup-aware stop behavior, and the daemon roadmap.

## 2026-06-07

- Added `docs/` knowledge hub with architecture, design, LLD, specs, structure, modules, code paths, workflow, rules, and conventions.

## Change Entry Format

- `YYYY-MM-DD`: summarize the documentation change, why it was made, and which docs were affected.
