# BlueMap Add-on Toolkit

BlueMap Add-on Toolkit centralizes the development checks repeated across the
independent BlueMap add-ons maintained by Jan Guenter. It does not contain a
renderer, an installed BlueMap add-on, candidate-mod code, or game assets.

The initial release provides:

- the versioned `addon-v1` repository contract;
- deterministic, clean-worktree convention migration;
- exact candidate-JAR verification from consumer-owned provenance;
- accepted staged-JAR entry verification.

## Run from a checkout

Python 3.11 or newer is sufficient:

```bash
PYTHONPATH=src python -m bluemap_addon_toolkit --help
PYTHONPATH=src python -m bluemap_addon_toolkit conventions check /path/to/addon
```

An installed checkout exposes the same interface as
`bluemap-addon-toolkit`.

## Commands

```text
bluemap-addon-toolkit conventions check REPOSITORY...
bluemap-addon-toolkit conventions migrate REPOSITORY... --check|--dry-run|--write
bluemap-addon-toolkit artifacts verify --manifest FILE --artifact KEY=JAR...
bluemap-addon-toolkit jar-entries verify --jar JAR --entries FILE --expected-version VERSION
bluemap-addon-toolkit jar-entries write --jar JAR --entries FILE
```

Artifact coordinates, expected sizes and hashes stay in each consumer's
`provenance/upstreams.json`. Accepted staging entries also remain in the
consumer. The toolkit owns the verification behavior, not the evidence.

## Version pinning

Consumer automation should install an immutable toolkit wheel by exact URL and
SHA-256. A source checkout must use a full commit:

```bash
git clone https://github.com/jan-guenter/bluemap-addon-toolkit.git
git -C bluemap-addon-toolkit checkout --detach FULL_COMMIT
```

Tags describe releases for people. Exact commits and release hashes remain the
automation trust boundary. See [adoption.md](docs/adoption.md) for the staged
migration policy.

The toolkit still excludes reusable workflows, gallery schemas, and
production Java. Those boundaries need their own artifact-parity pilots
before they can become shared interfaces.

## Gradle convention development

Release `0.2.0-alpha.1` adds a source-distributed convention plugin under
`gradle/`. Consumers load it from an exact toolkit Git submodule with a
consumer-owned trust preflight and `pluginManagement.includeBuild`, then
apply:

```groovy
plugins {
    id 'java-library'
    id 'checkstyle'
    id 'maven-publish'
    id 'io.github.janguenter.bluemap-addon.java-conventions'
}
```

The plugin owns only Java toolchain, compiler, archive reproducibility, test
framework and conditional Checkstyle configuration. Consumer plugins,
dependencies, repositories, coordinates, compression, packaging, provenance,
gallery and release rules stay in each add-on. See
[gradle-conventions.md](docs/gradle-conventions.md).

The toolkit is licensed under the [MIT License](LICENSE).
