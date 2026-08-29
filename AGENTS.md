# Agent guide for BlueMap Add-on Toolkit

This public repository owns development and release tooling shared by the
independent BlueMap add-ons maintained by Jan Guenter. Read this file and
`README.md` before changing it.

## Scope

- Keep the Python command-line package dependency-free at runtime and
  compatible with Python 3.11 or newer.
- Keep the toolkit development-only. It must never add a runtime dependency or
  runtime files to an add-on JAR.
- Preserve consumer-owned renderer code, gallery cases, candidate profiles,
  artifact identities, release provenance, and publication coordinates.
- Treat exact checks as contracts. Do not weaken a failure into a warning to
  make a new consumer pass.
- Prefer explicit versioned interfaces over repository-name inference.
- Pin every external GitHub Action to a full commit.

## Safety boundaries

Migration writes require a clean Git worktree and are limited to the files
reported by `--dry-run`. Artifact verification never downloads inputs.

Do not add candidate JARs, Minecraft assets, worlds, maps, credentials,
generated archives, or consumer release artifacts.

## Validation

Run:

```bash
python -m unittest discover -s tests -v
PYTHONPATH=src python -m bluemap_addon_toolkit --version
git diff --check
```

For a release, build the Python distributions twice, inspect their contents,
test installation in a clean virtual environment, and confirm that the tag is
exactly `v<version>`.
