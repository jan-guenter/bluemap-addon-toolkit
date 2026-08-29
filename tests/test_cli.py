"""Command-line behavior and extracted-script parity tests."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bluemap_addon_toolkit import cli  # noqa: E402
from fixture_factory import sha256, write_mod_jar  # noqa: E402


def invoke(arguments: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = cli.main(arguments)
    return status, stdout.getvalue(), stderr.getvalue()


class CliTest(unittest.TestCase):
    def test_artifact_success_matches_extracted_message(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jar = root / "fixture.jar"
            write_mod_jar(jar)
            manifest = root / "upstreams.json"
            manifest.write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "key": "fixture",
                                "size": jar.stat().st_size,
                                "sha256": sha256(jar),
                                "mod_id": "fixture",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            status, stdout, stderr = invoke(
                [
                    "artifacts",
                    "verify",
                    "--manifest",
                    str(manifest),
                    "--artifact",
                    f"fixture={jar}",
                ]
            )
            self.assertEqual(0, status)
            self.assertEqual(
                f"verified fixture: {jar.stat().st_size} bytes, SHA-256 {sha256(jar)}\n",
                stdout,
            )
            self.assertEqual("", stderr)

    def test_artifact_failure_has_stable_prefix_and_status(self) -> None:
        status, stdout, stderr = invoke(
            [
                "artifacts",
                "verify",
                "--manifest",
                "/does/not/exist",
            ]
        )
        self.assertEqual(1, status)
        self.assertEqual("", stdout)
        self.assertTrue(stderr.startswith("artifact verification failed: "))

    def test_jar_entries_write_and_verify_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jar = root / "fixture.jar"
            entries = root / "accepted.sha256"
            write_mod_jar(jar)
            status, stdout, stderr = invoke(
                [
                    "jar-entries",
                    "write",
                    "--jar",
                    str(jar),
                    "--entries",
                    str(entries),
                ]
            )
            self.assertEqual(0, status)
            self.assertRegex(stdout, r"^wrote \d+ accepted non-manifest entries to ")
            self.assertEqual("", stderr)
            status, stdout, stderr = invoke(
                [
                    "jar-entries",
                    "verify",
                    "--jar",
                    str(jar),
                    "--entries",
                    str(entries),
                    "--expected-version",
                    "1.2.3",
                ]
            )
            self.assertEqual(0, status)
            self.assertRegex(stdout, r"^staged equivalence passed: \d+ non-manifest entries\n$")
            self.assertEqual("", stderr)


if __name__ == "__main__":
    unittest.main()
