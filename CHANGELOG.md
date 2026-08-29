# Changelog

## 0.3.0-alpha.1 - 2026-08-29

- Make `conventions check` recognize the exact applied shared Gradle convention
  as the provider of its eight owned build settings.
- Keep legacy inline configuration valid and continue rejecting comments,
  other plugin IDs, declarations outside the leading plugin block, and
  `apply false`.

## 0.2.0-alpha.1 - 2026-08-29

- Add the source-distributed BlueMap add-on Java convention plugin and exact
  Gradle 9.4.0/9.6.1 fixture gate.
- Keep the convention build-only and consumer-neutral: it applies no plugins,
  production dependencies, repositories, publications, coordinates or
  release behavior.

## 0.1.0-alpha.1 - 2026-08-29

- Establish the development-only toolkit boundary.
- Add the `addon-v1` repository contract checker and deterministic migrator.
- Add exact candidate-artifact and staged-JAR identity verification.
