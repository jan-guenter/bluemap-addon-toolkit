# Adoption policy

Toolkit adoption is source-preserving work. A consumer migration must not
change renderer behavior, add-on version, an existing release tag, or an
accepted release artifact.

Use this sequence for each cohort:

1. Start from a clean worktree at the reviewed consumer commit.
2. Run `bluemap-addon-toolkit conventions migrate . --dry-run`, inspect every
   reported path, then use the same command with `--write` if the change is
   correct.
3. Run the consumer's existing complete gate before replacing a local tool.
4. Replace only a byte-exact or behaviorally tested duplicate.
5. Compare the production JAR's non-manifest entries with the accepted staging
   manifest. If the repository has a sealed release, verify the complete
   release gate as well.
6. Run the gallery generator, lint, package, and content comparison where the
   consumer has a gallery.
7. Submit the tooling-only change through a pull request. Do not move an
   existing release tag.

One passing consumer does not authorize a portfolio-wide rewrite. Promote a
cohort only after representatives with different build and gallery shapes
pass the same preservation gates.
