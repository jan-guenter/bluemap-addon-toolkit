#!/usr/bin/env python3
"""Build deterministic wheel and source archives with the declared backend."""

from __future__ import annotations

import argparse
from io import BytesIO
import gzip
import importlib.metadata
import os
from pathlib import Path
from pathlib import PurePosixPath
import sys
import tarfile


SOURCE_DATE_EPOCH = "315532800"
SETUPTOOLS_VERSION = "84.0.0"


def normalize_sdist(path: Path) -> None:
    """Repack the backend sdist with fixed metadata and a stable gzip header."""

    members: dict[str, tuple[bool, bytes]] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            name = member.name
            pure = PurePosixPath(name)
            if (
                not name
                or "\\" in name
                or any(ord(character) < 32 or ord(character) == 127 for character in name)
                or any(character in "\u0085\u2028\u2029" for character in name)
                or pure.is_absolute()
                or ".." in pure.parts
                or name in members
            ):
                raise ValueError(f"unsafe or duplicate sdist member: {name}")
            if member.isdir():
                members[name] = (True, b"")
            elif member.isfile():
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError(f"could not read sdist member: {name}")
                members[name] = (False, extracted.read())
            else:
                raise ValueError(f"unsupported sdist member type: {name}")

    temporary = path.with_name(f".{path.name}.normalized.tmp")
    try:
        with temporary.open("xb") as raw:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=9,
                fileobj=raw,
                mtime=int(SOURCE_DATE_EPOCH),
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed,
                    mode="w",
                    format=tarfile.PAX_FORMAT,
                ) as output:
                    for name, (is_directory, payload) in sorted(members.items()):
                        info = tarfile.TarInfo(name)
                        info.mtime = int(SOURCE_DATE_EPOCH)
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        info.mode = 0o755 if is_directory else 0o644
                        if is_directory:
                            info.type = tarfile.DIRTYPE
                            output.addfile(info)
                        else:
                            info.size = len(payload)
                            output.addfile(info, BytesIO(payload))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SOURCE_DATE_EPOCH", SOURCE_DATE_EPOCH)
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    actual_setuptools = importlib.metadata.version("setuptools")
    if actual_setuptools != SETUPTOOLS_VERSION:
        raise ValueError(
            f"setuptools {SETUPTOOLS_VERSION} is required, found {actual_setuptools}"
        )

    from setuptools import build_meta

    source = build_meta.build_sdist(str(output))
    normalize_sdist(output / source)
    wheel = build_meta.build_wheel(str(output))
    print(output / source)
    print(output / wheel)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"release build failed: {error}", file=sys.stderr)
        raise SystemExit(1)
