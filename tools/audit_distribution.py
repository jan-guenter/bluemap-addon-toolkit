#!/usr/bin/env python3
"""Audit toolkit release archives for their expected source-only boundary."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import stat
import tarfile
import zipfile


SOURCE_REQUIRED_SUFFIXES = {
    "docs/gradle-conventions.md",
    "gradle/build.gradle",
    "gradle/fixtures/java-checkstyle/build.gradle",
    "gradle/fixtures/java-checkstyle/config/checkstyle/checkstyle.xml",
    "gradle/fixtures/java-checkstyle/gradle.properties",
    "gradle/fixtures/java-checkstyle/settings.gradle",
    "gradle/fixtures/java-checkstyle/src/main/java/io/github/janguenter/fixture/Fixture.java",
    "gradle/fixtures/java-checkstyle/src/test/java/io/github/janguenter/fixture/FixtureTest.java",
    "gradle/fixtures/no-core-plugins/build.gradle",
    "gradle/fixtures/no-core-plugins/gradle.properties",
    "gradle/fixtures/no-core-plugins/settings.gradle",
    "gradle/settings.gradle",
    "gradle/src/main/java/io/github/janguenter/bluemap/addon/toolkit/gradle/BlueMapAddonJavaConventionsPlugin.java",
    "provenance/gradle-conventions.json",
    "src/bluemap_addon_toolkit/cli.py",
    "src/bluemap_addon_toolkit/data/addon-v1/checkstyle.xml",
    "provenance/origins.json",
    "requirements/build.txt",
    "tools/verify_gradle_conventions.py",
}
ARCHIVE_FORBIDDEN_SUFFIXES = (
    ".class",
    ".jar",
    ".png",
    ".pyc",
    ".zip",
)
WHEEL_FORBIDDEN_SUFFIXES = (
    ".gradle",
    ".groovy",
    ".java",
    ".kts",
)
ARCHIVE_FORBIDDEN_PARTS = {
    ".git",
    ".gradle",
    "build",
    "credentials",
    "dist",
    "logs",
    "mods",
    "world",
}


def safe(name: str) -> bool:
    path = PurePosixPath(name)
    first = path.parts[0] if path.parts else ""
    return (
        bool(name)
        and "\\" not in name
        and not any(ord(character) < 32 or ord(character) == 127 for character in name)
        and not any(character in "\u0085\u2028\u2029" for character in name)
        and not path.is_absolute()
        and not (len(first) == 2 and first[0].isalpha() and first[1] == ":")
        and ".." not in path.parts
    )


def names(path: Path) -> set[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            result = set()
            for info in archive.infolist():
                if info.is_dir():
                    continue
                mode = info.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if (
                    not safe(info.filename)
                    or info.filename in result
                    or kind not in {0, stat.S_IFREG}
                ):
                    raise ValueError(f"unsafe or duplicate wheel path: {info.filename}")
                result.add(info.filename)
            return result
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            result = set()
            for member in archive.getmembers():
                if member.isdir():
                    continue
                if (
                    not member.isfile()
                    or not safe(member.name)
                    or member.name in result
                ):
                    raise ValueError(f"unsafe source archive member: {member.name}")
                result.add(member.name)
            return result
    raise ValueError(f"unsupported distribution: {path}")


def audit(path: Path) -> None:
    members = names(path)
    is_source = path.name.endswith(".tar.gz")
    for name in members:
        member = PurePosixPath(name)
        if name.endswith(ARCHIVE_FORBIDDEN_SUFFIXES) or ARCHIVE_FORBIDDEN_PARTS.intersection(
            member.parts
        ):
            raise ValueError(f"forbidden distribution member: {name}")
        if not is_source and (
            name.endswith(WHEEL_FORBIDDEN_SUFFIXES) or "gradle" in member.parts
        ):
            raise ValueError(f"Gradle source leaked into wheel: {name}")
    if is_source:
        roots = {PurePosixPath(name).parts[0] for name in members}
        if len(roots) != 1:
            raise ValueError(f"source archive has multiple roots: {sorted(roots)}")
        for required in SOURCE_REQUIRED_SUFFIXES:
            if not any(name.endswith("/" + required) for name in members):
                raise ValueError(f"source archive is missing {required}")
    else:
        required = {
            "bluemap_addon_toolkit/cli.py",
            "bluemap_addon_toolkit/data/addon-v1/checkstyle.xml",
        }
        missing = sorted(required - members)
        if missing:
            raise ValueError(f"wheel is missing {missing}")
        if not any(
            name.endswith("/share/bluemap-addon-toolkit/provenance/origins.json")
            for name in members
        ):
            raise ValueError("wheel is missing provenance/origins.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args()
    for archive in args.archives:
        audit(archive)
        print(f"audited {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
