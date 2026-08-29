"""Accepted non-manifest JAR entry identities."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re
import zipfile


LINE = re.compile(r"([0-9a-f]{64})  ([^\r\n]+)")
MANIFEST = "META-INF/MANIFEST.MF"


def safe_entry(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and "\\" not in name
        and not any(ord(character) < 32 or ord(character) == 127 for character in name)
        and not any(character in "\u0085\u2028\u2029" for character in name)
        and not path.is_absolute()
        and ".." not in path.parts
    )


def load_entries(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"invalid entry manifest line {number}")
        entry_digest, name = match.groups()
        if not safe_entry(name) or name in result:
            raise ValueError(f"unsafe or duplicate entry on line {number}: {name}")
        result[name] = entry_digest
    if not result:
        raise ValueError("accepted staging entry manifest is empty")
    return result


def jar_entries(archive: zipfile.ZipFile) -> dict[str, str]:
    result: dict[str, str] = {}
    manifests = 0
    for info in archive.infolist():
        name = info.filename
        if name == MANIFEST:
            manifests += 1
            if info.is_dir():
                raise ValueError("release JAR manifest is not a regular entry")
            continue
        if info.is_dir():
            continue
        if not safe_entry(name) or name in result:
            raise ValueError(f"unsafe or duplicate JAR entry: {name}")
        result[name] = hashlib.sha256(archive.read(info)).hexdigest()
    if manifests != 1:
        raise ValueError(f"release JAR must contain exactly one {MANIFEST}")
    if not result:
        raise ValueError("JAR contains no accepted non-manifest entries")
    return result


def write_entries(jar: Path, entries: Path) -> str:
    with zipfile.ZipFile(jar) as archive:
        accepted = jar_entries(archive)
    payload = "".join(
        f"{entry_digest}  {name}\n"
        for name, entry_digest in sorted(accepted.items())
    )
    try:
        with entries.open("x", encoding="utf-8", newline="\n") as output:
            output.write(payload)
    except FileExistsError as error:
        raise ValueError(f"refusing to overwrite accepted entries: {entries}") from error
    return f"wrote {len(accepted)} accepted non-manifest entries to {entries}"


def manifest_version(archive: zipfile.ZipFile) -> str:
    manifests = [info for info in archive.infolist() if info.filename == MANIFEST]
    if len(manifests) != 1 or manifests[0].is_dir():
        raise ValueError(f"release JAR must contain exactly one {MANIFEST}")
    payload = archive.read(manifests[0])
    manifest = payload.decode("utf-8", errors="strict")
    attributes: dict[str, str] = {}
    current: str | None = None
    for line in manifest.splitlines():
        if not line:
            break
        if line.startswith(" "):
            if current is None:
                raise ValueError("release JAR manifest has an orphan continuation")
            attributes[current] += line[1:]
            continue
        name, separator, value = line.partition(": ")
        if not separator or not name or name in attributes:
            raise ValueError("release JAR manifest main section is malformed")
        attributes[name] = value
        current = name
    if "Implementation-Version" in attributes:
        return attributes["Implementation-Version"]
    raise ValueError("release JAR manifest lacks Implementation-Version")


def verify_entries(jar: Path, entries: Path, expected_version: str) -> str:
    expected = load_entries(entries)
    with zipfile.ZipFile(jar) as archive:
        actual = jar_entries(archive)
        if set(actual) != set(expected):
            raise ValueError(
                f"entry set differs: missing={sorted(set(expected) - set(actual))}, "
                f"extra={sorted(set(actual) - set(expected))}"
            )
        for name, accepted_sha256 in sorted(expected.items()):
            if actual[name] != accepted_sha256:
                raise ValueError(f"accepted staging entry differs: {name}: {actual[name]}")
        actual_version = manifest_version(archive)
    if actual_version != expected_version:
        raise ValueError(
            f"release manifest version differs: {actual_version!r} != {expected_version!r}"
        )
    return f"staged equivalence passed: {len(expected)} non-manifest entries"
