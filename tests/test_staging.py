"""Tests for accepted staged-JAR entry identities."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bluemap_addon_toolkit import staging  # noqa: E402
from fixture_factory import write_mod_jar  # noqa: E402


class StagingTest(unittest.TestCase):
    def test_round_trip_is_sorted_lf_and_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jar = root / "fixture.jar"
            entries = root / "accepted.sha256"
            write_mod_jar(jar, version="2.0.0", extra_entries={"a/First": b"first"})
            message = staging.write_entries(jar, entries)
            self.assertIn("accepted non-manifest entries", message)
            payload = entries.read_bytes()
            self.assertTrue(payload.endswith(b"\n"))
            self.assertNotIn(b"\r", payload)
            names = [line.split("  ", 1)[1] for line in payload.decode().splitlines()]
            self.assertEqual(sorted(names), names)
            self.assertEqual(
                f"staged equivalence passed: {len(names)} non-manifest entries",
                staging.verify_entries(jar, entries, "2.0.0"),
            )
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                staging.write_entries(jar, entries)

    def test_rejects_traversal_and_duplicate_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            unsafe = root / "unsafe.jar"
            with zipfile.ZipFile(unsafe, "w") as archive:
                archive.writestr("../escape", b"bad")
            with zipfile.ZipFile(unsafe) as archive:
                with self.assertRaisesRegex(ValueError, "unsafe or duplicate"):
                    staging.jar_entries(archive)

            duplicate = root / "duplicate.jar"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(duplicate, "w") as archive:
                    archive.writestr("same", b"one")
                    archive.writestr("same", b"two")
            with zipfile.ZipFile(duplicate) as archive:
                with self.assertRaisesRegex(ValueError, "unsafe or duplicate"):
                    staging.jar_entries(archive)

            control = root / "control.jar"
            with zipfile.ZipFile(control, "w") as archive:
                archive.writestr(
                    staging.MANIFEST,
                    "Manifest-Version: 1.0\r\nImplementation-Version: 1.0\r\n\r\n",
                )
                archive.writestr("bad\nname", b"bad")
            with zipfile.ZipFile(control) as archive:
                with self.assertRaisesRegex(ValueError, "unsafe or duplicate"):
                    staging.jar_entries(archive)

            unicode_line = root / "unicode-line.jar"
            with zipfile.ZipFile(unicode_line, "w") as archive:
                archive.writestr(
                    staging.MANIFEST,
                    "Manifest-Version: 1.0\r\nImplementation-Version: 1.0\r\n\r\n",
                )
                archive.writestr("bad\u2028name", b"bad")
            with zipfile.ZipFile(unicode_line) as archive:
                with self.assertRaisesRegex(ValueError, "unsafe or duplicate"):
                    staging.jar_entries(archive)

    def test_rejects_malformed_entry_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            entries = Path(temporary) / "accepted.sha256"
            for payload in ("", "not a digest\n", f"{'0' * 64}  ../bad\n"):
                with self.subTest(payload=payload):
                    entries.write_text(payload, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        staging.load_entries(entries)

    def test_rejects_missing_or_wrong_implementation_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jar = root / "fixture.jar"
            entries = root / "accepted.sha256"
            write_mod_jar(jar, version="1.0.0")
            staging.write_entries(jar, entries)
            with self.assertRaisesRegex(ValueError, "release manifest version differs"):
                staging.verify_entries(jar, entries, "1.0.1")

            missing = root / "missing.jar"
            with zipfile.ZipFile(missing, "w") as archive:
                archive.writestr("payload", b"data")
            with zipfile.ZipFile(missing) as archive:
                with self.assertRaisesRegex(ValueError, "exactly one META-INF/MANIFEST.MF"):
                    staging.manifest_version(archive)

    def test_rejects_duplicate_manifest_and_ignores_named_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = root / "duplicate-manifest.jar"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(duplicate, "w") as archive:
                    archive.writestr(
                        staging.MANIFEST,
                        "Manifest-Version: 1.0\r\nImplementation-Version: 1.0\r\n\r\n",
                    )
                    archive.writestr(
                        staging.MANIFEST,
                        "Manifest-Version: 1.0\r\nImplementation-Version: 2.0\r\n\r\n",
                    )
                    archive.writestr("payload", b"data")
            with zipfile.ZipFile(duplicate) as archive:
                with self.assertRaisesRegex(ValueError, "exactly one META-INF/MANIFEST.MF"):
                    staging.jar_entries(archive)

            named = root / "named-section.jar"
            with zipfile.ZipFile(named, "w") as archive:
                archive.writestr(
                    staging.MANIFEST,
                    "Manifest-Version: 1.0\r\n\r\n"
                    "Name: payload\r\nImplementation-Version: 1.2.3\r\n\r\n",
                )
                archive.writestr("payload", b"data")
            with zipfile.ZipFile(named) as archive:
                with self.assertRaisesRegex(ValueError, "lacks Implementation-Version"):
                    staging.manifest_version(archive)


if __name__ == "__main__":
    unittest.main()
