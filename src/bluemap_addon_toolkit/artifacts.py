"""Exact candidate artifact verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zipfile


DESCRIPTOR = "META-INF/neoforge.mods.toml"
MAX_DESCRIPTOR_BYTES = 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}")


def parse_artifact(value: str) -> tuple[str, Path]:
    key, separator, path = value.partition("=")
    if not separator or not key or not path:
        raise ValueError(f"artifact must be KEY=PATH: {value!r}")
    return key, Path(path)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def declares_mod(path: Path, expected_mod_id: str) -> bool:
    declaration = re.compile(
        r"^(?:modId|\"modId\"|'modId')\s*=\s*"
        + rf"(?:\"{re.escape(expected_mod_id)}\"|'"
        + re.escape(expected_mod_id)
        + r"')$"
    )
    with zipfile.ZipFile(path) as archive:
        descriptors = [info for info in archive.infolist() if info.filename == DESCRIPTOR]
        if len(descriptors) != 1:
            return False
        info = descriptors[0]
        if info.is_dir() or info.file_size > MAX_DESCRIPTOR_BYTES:
            return False
        payload = archive.read(info)
    if len(payload) > MAX_DESCRIPTOR_BYTES:
        return False
    descriptor = payload.decode("utf-8", errors="strict")
    in_mods = False
    for line in descriptor.removeprefix("\ufeff").splitlines():
        statement = line.split("#", 1)[0].strip()
        if statement.startswith("["):
            in_mods = statement in {"[[mods]]", "[[\"mods\"]]", "[['mods']]"}
        elif in_mods and declaration.fullmatch(statement):
            return True
    return False


def load_pins(path: Path) -> dict[str, dict[str, object]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("manifest artifacts must be a non-empty array")
    pins: dict[str, dict[str, object]] = {}
    for index, row in enumerate(artifacts):
        if not isinstance(row, dict):
            raise ValueError(f"artifact row {index} is not an object")
        key = row.get("key")
        size = row.get("size")
        sha256 = row.get("sha256")
        mod_id = row.get("mod_id")
        if not isinstance(key, str) or not key:
            raise ValueError(f"artifact row {index} has no key")
        if key in pins:
            raise ValueError(f"duplicate artifact key: {key}")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError(f"{key} has invalid size")
        if not isinstance(sha256, str) or not SHA256.fullmatch(sha256):
            raise ValueError(f"{key} has invalid SHA-256")
        if not isinstance(mod_id, str) or not mod_id:
            raise ValueError(f"{key} has invalid mod ID")
        pins[key] = row
    return pins


def verify_artifacts(manifest: Path, artifact_values: list[str]) -> list[str]:
    pins = load_pins(manifest)
    supplied_pairs = [parse_artifact(value) for value in artifact_values]
    supplied = dict(supplied_pairs)
    if len(supplied) != len(supplied_pairs):
        raise ValueError("artifact keys must be unique")
    if set(supplied) != set(pins):
        raise ValueError(
            f"artifact key mismatch: supplied={sorted(supplied)}, expected={sorted(pins)}"
        )

    messages: list[str] = []
    for key, pin in sorted(pins.items()):
        path = supplied[key]
        if not path.is_file():
            raise ValueError(f"artifact is not a file: {path}")
        actual_size = path.stat().st_size
        actual_sha256 = digest(path)
        if actual_size != pin["size"] or actual_sha256 != pin["sha256"]:
            raise ValueError(
                f"{key} byte identity mismatch: {actual_size} bytes, "
                f"SHA-256 {actual_sha256}"
            )
        if not declares_mod(path, str(pin["mod_id"])):
            raise ValueError(f"{key} does not declare exact mod ID {pin['mod_id']}")
        messages.append(
            f"verified {key}: {actual_size} bytes, SHA-256 {actual_sha256}"
        )
    return messages
