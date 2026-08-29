"""Tests for exact candidate artifact verification."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bluemap_addon_toolkit import artifacts  # noqa: E402
from fixture_factory import sha256, write_mod_jar  # noqa: E402


class ArtifactTest(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
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
                            "unused_provenance_field": "retained by consumer",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return jar, manifest

    def test_verifies_exact_bytes_and_mod_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            jar, manifest = self.fixture(Path(temporary))
            self.assertEqual(
                [
                    f"verified fixture: {jar.stat().st_size} bytes, "
                    f"SHA-256 {sha256(jar)}"
                ],
                artifacts.verify_artifacts(manifest, [f"fixture={jar}"]),
            )

    def test_rejects_wrong_hash_and_key_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            jar, manifest = self.fixture(Path(temporary))
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["artifacts"][0]["sha256"] = "0" * 64
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "byte identity mismatch"):
                artifacts.verify_artifacts(manifest, [f"fixture={jar}"])
            with self.assertRaisesRegex(ValueError, "artifact key mismatch"):
                artifacts.verify_artifacts(manifest, [f"other={jar}"])

    def test_rejects_duplicate_supplied_and_manifest_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jar, manifest = self.fixture(root)
            with self.assertRaisesRegex(ValueError, "artifact keys must be unique"):
                artifacts.verify_artifacts(
                    manifest,
                    [f"fixture={jar}", f"fixture={jar}"],
                )
            row = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"][0]
            manifest.write_text(json.dumps({"artifacts": [row, row]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate artifact key"):
                artifacts.load_pins(manifest)

    def test_rejects_duplicate_or_oversized_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = root / "duplicate.jar"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(duplicate, "w") as archive:
                    archive.writestr(artifacts.DESCRIPTOR, '[[mods]]\nmodId="fixture"\n')
                    archive.writestr(artifacts.DESCRIPTOR, '[[mods]]\nmodId="fixture"\n')
            self.assertFalse(artifacts.declares_mod(duplicate, "fixture"))

            oversized = root / "oversized.jar"
            with zipfile.ZipFile(oversized, "w") as archive:
                archive.writestr(
                    artifacts.DESCRIPTOR,
                    b"x" * (artifacts.MAX_DESCRIPTOR_BYTES + 1),
                )
            self.assertFalse(artifacts.declares_mod(oversized, "fixture"))

    def test_rejects_invalid_manifest_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "upstreams.json"
            invalid_rows = (
                {},
                {"artifacts": []},
                {"artifacts": [{"key": "x", "size": True, "sha256": "0" * 64, "mod_id": "x"}]},
                {"artifacts": [{"key": "x", "size": 1, "sha256": "BAD", "mod_id": "x"}]},
            )
            for value in invalid_rows:
                with self.subTest(value=value):
                    manifest.write_text(json.dumps(value), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        artifacts.load_pins(manifest)


if __name__ == "__main__":
    unittest.main()
