"""Small generated fixtures for toolkit tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import zipfile


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_mod_jar(
    path: Path,
    *,
    mod_id: str = "fixture",
    version: str = "1.2.3",
    extra_entries: dict[str, bytes] | None = None,
) -> None:
    manifest = (
        "Manifest-Version: 1.0\r\n"
        f"Implementation-Version: {version}\r\n"
        "\r\n"
    ).encode()
    descriptor = f'[[mods]]\nmodId="{mod_id}"\n'.encode()
    entries = {
        "META-INF/MANIFEST.MF": manifest,
        "META-INF/neoforge.mods.toml": descriptor,
        "example/Fixture.class": b"fixture class bytes",
    }
    entries.update(extra_entries or {})
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)


def init_git(repository: Path) -> None:
    subprocess.run(["git", "-C", str(repository), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repository), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
