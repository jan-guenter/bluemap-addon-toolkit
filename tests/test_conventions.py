"""Tests for the addon-v1 checker and deterministic migration."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bluemap_addon_toolkit import cli, contract, migration  # noqa: E402
from fixture_factory import init_git  # noqa: E402


class ConventionTest(unittest.TestCase):
    INLINE_BUILD = """plugins {
    id 'java-library'
    id 'checkstyle'
    id 'maven-publish'
}
java { toolchain.languageVersion = JavaLanguageVersion.of(21) }
tasks.withType(JavaCompile).configureEach {
    options.release = 21
    options.encoding = 'UTF-8'
    options.compilerArgs.addAll(['-Xlint:all', '-Werror'])
}
checkstyle { toolVersion = '10.18.2' }
tasks.withType(AbstractArchiveTask).configureEach {
    preserveFileTimestamps = false
    reproducibleFileOrder = true
}
"""

    SHARED_PLUGIN_BUILD = """plugins {
    id 'java-library'
    id 'checkstyle'
    id 'maven-publish'
    id 'io.github.janguenter.bluemap-addon.java-conventions'
}
"""

    def write_minimal_repository(
        self,
        repository: Path,
        *,
        build: str | None = None,
    ) -> None:
        required_plain = set(contract.REQUIRED_PATHS) - {
            ".editorconfig",
            ".gitattributes",
            "config/checkstyle/checkstyle.xml",
            "build.gradle",
            "gradle.properties",
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
        }
        for relative in required_plain:
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture for {relative}\n", encoding="utf-8")
        for relative, standard in contract.STANDARD_FILES.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contract.standard_bytes(standard))
        (repository / "build.gradle").write_text(
            self.INLINE_BUILD if build is None else build,
            encoding="utf-8",
        )
        (repository / "gradle.properties").write_text(
            """addon_group=io.github.janguenter.bluemap
addon_id=fixture
addon_name=Fixture
addon_version=0.1.0-alpha.1
artifact_id=bluemap-fixture-addon
bluemap_version=5.22-test
org.gradle.configuration-cache=true
org.gradle.daemon=false
org.gradle.jvmargs=-Xmx2G
""",
            encoding="utf-8",
        )
        workflow = (
            "steps:\n"
            "  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1\n"
        )
        for relative in (
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
        ):
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(workflow, encoding="utf-8")
        java = repository / "src/main/java/io/github/janguenter/bluemap/fixture/Fixture.java"
        java.parent.mkdir(parents=True, exist_ok=True)
        java.write_text(
            "package io.github.janguenter.bluemap.fixture;\n\n"
            "public final class Fixture {\n}\n",
            encoding="utf-8",
        )

    def test_complete_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.write_minimal_repository(repository)
            init_git(repository)
            result = contract.check_repository(repository)
            self.assertTrue(result["ok"], result["findings"])

    def test_applied_shared_convention_fixture_passes(self) -> None:
        builds = {
            "single quotes": self.SHARED_PLUGIN_BUILD,
            "double quotes": self.SHARED_PLUGIN_BUILD.replace(
                "id 'io.github.janguenter.bluemap-addon.java-conventions'",
                'id "io.github.janguenter.bluemap-addon.java-conventions"',
            ),
            "leading comment": "// consumer build\n" + self.SHARED_PLUGIN_BUILD,
        }
        for name, build in builds.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary)
                self.write_minimal_repository(repository, build=build)
                init_git(repository)
                result = contract.check_repository(repository)
                self.assertTrue(result["ok"], result["findings"])

    def test_only_applied_canonical_shared_convention_satisfies_owned_checks(self) -> None:
        invalid_builds = {
            "apply false": self.SHARED_PLUGIN_BUILD.replace(
                "java-conventions'",
                "java-conventions' apply false",
            ),
            "apply true": self.SHARED_PLUGIN_BUILD.replace(
                "java-conventions'",
                "java-conventions' apply true",
            ),
            "version suffix": self.SHARED_PLUGIN_BUILD.replace(
                "java-conventions'",
                "java-conventions' version '0.3.0-alpha.1'",
            ),
            "commented": self.SHARED_PLUGIN_BUILD.replace(
                "    id 'io.github.janguenter.bluemap-addon.java-conventions'",
                "    // id 'io.github.janguenter.bluemap-addon.java-conventions'",
            ),
            "trailing comment": self.SHARED_PLUGIN_BUILD.replace(
                "java-conventions'",
                "java-conventions' // not the canonical declaration",
            ),
            "block commented": self.SHARED_PLUGIN_BUILD.replace(
                "    id 'io.github.janguenter.bluemap-addon.java-conventions'",
                "    /* id 'io.github.janguenter.bluemap-addon.java-conventions' */",
            ),
            "multiline string": self.SHARED_PLUGIN_BUILD.replace(
                "    id 'io.github.janguenter.bluemap-addon.java-conventions'",
                "    def ignored = \"\"\"\n"
                "    id 'io.github.janguenter.bluemap-addon.java-conventions'\n"
                "    \"\"\"",
            ),
            "misspelled": self.SHARED_PLUGIN_BUILD.replace(
                "java-conventions'",
                "java-convention'",
            ),
            "wrong case": self.SHARED_PLUGIN_BUILD.replace(
                "bluemap-addon.java-conventions'",
                "bluemap-addon.Java-conventions'",
            ),
            "prefix": self.SHARED_PLUGIN_BUILD.replace(
                "io.github.janguenter",
                "invalid.io.github.janguenter",
            ),
            "suffix": self.SHARED_PLUGIN_BUILD.replace(
                "java-conventions'",
                "java-conventions.invalid'",
            ),
            "legacy apply plugin": self.SHARED_PLUGIN_BUILD.replace(
                "    id 'io.github.janguenter.bluemap-addon.java-conventions'",
                "    apply plugin: 'io.github.janguenter.bluemap-addon.java-conventions'",
            ),
            "parenthesized": self.SHARED_PLUGIN_BUILD.replace(
                "    id 'io.github.janguenter.bluemap-addon.java-conventions'",
                "    id('io.github.janguenter.bluemap-addon.java-conventions')",
            ),
            "semicolon": self.SHARED_PLUGIN_BUILD.replace(
                "java-conventions'",
                "java-conventions';",
            ),
            "mismatched quotes": self.SHARED_PLUGIN_BUILD.replace(
                "id 'io.github.janguenter.bluemap-addon.java-conventions'",
                "id 'io.github.janguenter.bluemap-addon.java-conventions\"",
            ),
            "outside plugin block": self.SHARED_PLUGIN_BUILD.replace(
                "    id 'io.github.janguenter.bluemap-addon.java-conventions'\n",
                "",
            )
            + "id 'io.github.janguenter.bluemap-addon.java-conventions'\n",
        }
        expected = sorted(
            message for _pattern, message in contract.CONVENTION_OWNED_BUILD_CHECKS
        )
        for name, build in invalid_builds.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                repository = Path(temporary)
                self.write_minimal_repository(repository, build=build)
                init_git(repository)
                result = contract.check_repository(repository)
                actual = [item["message"] for item in result["findings"]]
                self.assertEqual(expected, actual)

    def test_shared_convention_does_not_replace_consumer_plugins(self) -> None:
        build = """plugins {
    id 'io.github.janguenter.bluemap-addon.java-conventions'
}
"""
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.write_minimal_repository(repository, build=build)
            init_git(repository)
            result = contract.check_repository(repository)
            expected = sorted(message for _pattern, message in contract.CONSUMER_BUILD_CHECKS)
            actual = [item["message"] for item in result["findings"]]
            self.assertEqual(expected, actual)

    def test_cli_accepts_applied_shared_convention_in_text_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            self.write_minimal_repository(repository, build=self.SHARED_PLUGIN_BUILD)
            init_git(repository)
            for output_format in ("text", "json"):
                with self.subTest(output_format=output_format):
                    arguments = ["conventions", "check", str(repository)]
                    if output_format == "json":
                        arguments.append("--json")
                    stdout = StringIO()
                    stderr = StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        status = cli.main(arguments)
                    self.assertEqual(0, status)
                    self.assertEqual("", stderr.getvalue())
                    if output_format == "json":
                        result = json.loads(stdout.getvalue())
                        self.assertEqual(1, len(result))
                        self.assertTrue(result[0]["ok"])
                        self.assertEqual([], result[0]["findings"])
                    else:
                        self.assertEqual(
                            f"PASS {repository.resolve()}\n"
                            "1/1 repositories satisfy addon-v1\n",
                            stdout.getvalue(),
                        )

    def test_reports_missing_contract_and_unpinned_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            subprocess.run(["git", "-C", str(repository), "init", "-q"], check=True)
            workflow = repository / ".github/workflows/ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text("steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
            result = contract.check_repository(repository)
            messages = [item["message"] for item in result["findings"]]
            self.assertFalse(result["ok"])
            self.assertIn("required file is missing", messages)
            self.assertIn(
                "action is not pinned to a full commit: actions/checkout@v4",
                messages,
            )

    def test_migration_is_deterministic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "gradle.properties").write_text(
                "addon_id=fixture\n"
                "addon_name=Fixture\n"
                "addon_version=0.1.0-alpha.1\n"
                "bluemap_version=5.22-test\n",
                encoding="utf-8",
            )
            (repository / "build.gradle").write_text(
                "plugins {\n    id 'java-library'\n    id 'maven-publish'\n}\n\n"
                "tasks.named('jar', Jar).configure {\n}\n",
                encoding="utf-8",
            )
            init_git(repository)
            first = migration.planned_changes(repository)
            second = migration.planned_changes(repository)
            self.assertEqual(first, second)
            pending = migration.migrate_repository(repository, write=True)
            self.assertTrue(pending)
            self.assertEqual([], migration.migrate_repository(repository, write=False))
            self.assertIn("id 'checkstyle'", (repository / "build.gradle").read_text())

    def test_migration_write_refuses_dirty_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "gradle.properties").write_text(
                "addon_id=fixture\n"
                "addon_name=Fixture\n"
                "addon_version=0.1.0-alpha.1\n"
                "bluemap_version=5.22-test\n",
                encoding="utf-8",
            )
            (repository / "build.gradle").write_text(
                "plugins {\n    id 'java-library'\n}\n",
                encoding="utf-8",
            )
            init_git(repository)
            (repository / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "refusing dirty repository"):
                migration.migrate_repository(repository, write=True)

    def test_migration_rejects_symlinked_parent_without_external_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            external = root / "external"
            repository.mkdir()
            external.mkdir()
            (repository / "gradle.properties").write_text(
                "addon_id=fixture\n"
                "addon_name=Fixture\n"
                "addon_version=0.1.0-alpha.1\n"
                "bluemap_version=5.22-test\n",
                encoding="utf-8",
            )
            (repository / "build.gradle").write_text(
                "plugins {\n    id 'java-library'\n}\n",
                encoding="utf-8",
            )
            (repository / "config").symlink_to(external, target_is_directory=True)
            init_git(repository)
            with self.assertRaisesRegex(ValueError, "parent must not be a symlink"):
                migration.migrate_repository(repository, write=True)
            self.assertFalse((external / "checkstyle" / "checkstyle.xml").exists())

    def test_migration_rejects_directory_at_missing_only_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            (repository / "gradle.properties").write_text(
                "addon_id=fixture\n"
                "addon_name=Fixture\n"
                "addon_version=0.1.0-alpha.1\n"
                "bluemap_version=5.22-test\n",
                encoding="utf-8",
            )
            (repository / "build.gradle").write_text(
                "plugins {\n    id 'java-library'\n}\n",
                encoding="utf-8",
            )
            (repository / "AGENTS.md").mkdir()
            init_git(repository)
            with self.assertRaisesRegex(ValueError, "managed path is not a regular file"):
                migration.migrate_repository(repository, write=False)

    def test_contract_does_not_follow_required_file_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "repository"
            repository.mkdir()
            self.write_minimal_repository(repository)
            external = root / "external-readme.md"
            external.write_text("external\n", encoding="utf-8")
            (repository / "README.md").unlink()
            (repository / "README.md").symlink_to(external)
            init_git(repository)
            result = contract.check_repository(repository)
            self.assertIn(
                {"path": "README.md", "message": "required file is missing"},
                result["findings"],
            )

    def test_standard_files_are_self_consistent(self) -> None:
        self.assertTrue(contract.standard_bytes("editorconfig").endswith(b"\n"))
        self.assertTrue(contract.standard_bytes("gitattributes").endswith(b"\n"))
        checkstyle = contract.standard_bytes("checkstyle.xml").decode()
        self.assertNotIn('module name="UnusedImports"', checkstyle)
        self.assertIn('module name="NeedBraces"', checkstyle)


if __name__ == "__main__":
    unittest.main()
