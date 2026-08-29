# Releasing the toolkit

The toolkit is development-only, but its version is part of consumer build and
release evidence. Release from a clean reviewed commit.

1. Run all tests, the 51-repository contract gate, `actionlint`, and
   `git diff --check`.
2. Install the exact backend from `requirements/build.txt`, build twice with
   `tools/build_release.py`, and compare both archives byte for byte.
3. Run `tools/audit_distribution.py` on the wheel and source archive. Confirm
   that neither contains JARs, game assets, credentials, generated consumer
   data, or runtime BlueMap classes.
4. Confirm `pyproject.toml` and `src/bluemap_addon_toolkit/version.py` describe
   the same release and update `CHANGELOG.md`.
5. Merge through a pull request, then create an immutable annotated tag exactly
   equal to `v<version>`.
6. Let the release workflow create an attested draft, compare its downloaded
   assets, and publish it. Alpha versions remain GitHub prereleases.

Consumers pin the full release commit and the exact wheel SHA-256. No toolkit
release updates a Minecraft server.

The human version `0.1.0-alpha.1` is normalized to the PEP 440 distribution
version `0.1.0a1` in wheel and source-archive filenames.
