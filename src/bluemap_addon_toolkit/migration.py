"""Deterministic rendering of managed addon-v1 convention files."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .contract import PROPERTY, standard_bytes


@dataclass(frozen=True)
class Change:
    """A complete file replacement planned by the migrator."""

    path: str
    content: bytes
    only_if_missing: bool = False


def git_status(repository: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "status", "--porcelain"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"cannot inspect {repository}")
    return result.stdout


def properties(repository: Path) -> dict[str, str]:
    path = repository / "gradle.properties"
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{repository}: gradle.properties is not a regular file")
    return dict(PROPERTY.findall(path.read_text(encoding="utf-8")))


def render(template: str, values: dict[str, str]) -> bytes:
    text = template
    for key, value in values.items():
        text = text.replace(f"@@{key}@@", value)
    unresolved = sorted(set(re.findall(r"@@[A-Z0-9_]+@@", text)))
    if unresolved:
        raise ValueError(f"unresolved template tokens: {unresolved}")
    return text.encode("utf-8")


def insert_checkstyle(build: str) -> str:
    if re.search(r"id\s+['\"]checkstyle['\"]", build):
        return build
    updated, count = re.subn(
        r"(plugins\s*\{\s*\n\s*id\s+['\"]java-library['\"]\s*\n)",
        r"\1    id 'checkstyle'\n",
        build,
        count=1,
    )
    if count != 1:
        raise ValueError("could not insert checkstyle plugin")
    block = """

checkstyle {
    toolVersion = '10.18.2'
    configFile = file('config/checkstyle/checkstyle.xml')
}

tasks.withType(Checkstyle).configureEach {
    reports {
        xml.required = true
        html.required = true
    }
}
"""
    anchor = "tasks.named('jar', Jar).configure {"
    if anchor in updated:
        return updated.replace(anchor, block + "\n" + anchor, 1)
    return updated.rstrip() + block + "\n"


def planned_changes(repository: Path) -> list[Change]:
    values = properties(repository)
    required = {
        "ADDON_ID": values.get("addon_id", ""),
        "ADDON_NAME": values.get("addon_name", ""),
        "ADDON_VERSION": values.get("addon_version", ""),
        "BLUEMAP_VERSION": values.get("bluemap_version", ""),
    }
    if not all(required.values()):
        raise ValueError(f"{repository}: required add-on properties are incomplete")
    changes = [
        Change(".editorconfig", standard_bytes("editorconfig")),
        Change(".gitattributes", standard_bytes("gitattributes")),
        Change("config/checkstyle/checkstyle.xml", standard_bytes("checkstyle.xml")),
        Change(
            "AGENTS.md",
            render(standard_bytes("AGENTS.md.template").decode(), required),
            only_if_missing=True,
        ),
        Change(
            "docs/RELEASING.md",
            standard_bytes("RELEASING.md.template"),
            only_if_missing=True,
        ),
    ]
    build_path = repository / "build.gradle"
    if build_path.is_symlink() or not build_path.is_file():
        raise ValueError(f"{repository}: build.gradle is not a regular file")
    build = build_path.read_text(encoding="utf-8")
    updated = insert_checkstyle(build)
    if updated != build:
        changes.append(Change("build.gradle", updated.encode("utf-8")))
    return changes


def differences(repository: Path, changes: list[Change]) -> list[Change]:
    result: list[Change] = []
    for change in changes:
        relative = Path(change.path)
        validate_existing_parent(repository, relative)
        path = repository / relative
        if path.is_symlink():
            raise ValueError(f"managed path must not be a symlink: {path}")
        if change.only_if_missing and path.exists():
            if not path.is_file():
                raise ValueError(f"managed path is not a regular file: {path}")
            continue
        if not path.is_file() or path.read_bytes() != change.content:
            result.append(change)
    return result


def validate_existing_parent(repository: Path, relative: Path) -> None:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"managed path escapes repository: {relative}")
    parent = repository
    for part in relative.parts[:-1]:
        parent = parent / part
        if parent.is_symlink():
            raise ValueError(f"managed path parent must not be a symlink: {parent}")
        if not parent.exists():
            return
        if not parent.is_dir():
            raise ValueError(f"managed path parent is not a directory: {parent}")


def prepare_parent(repository: Path, relative: Path) -> Path:
    validate_existing_parent(repository, relative)
    parent = repository
    for part in relative.parts[:-1]:
        parent = parent / part
        if parent.is_symlink():
            raise ValueError(f"managed path parent must not be a symlink: {parent}")
        if parent.exists():
            if not parent.is_dir():
                raise ValueError(f"managed path parent is not a directory: {parent}")
        else:
            parent.mkdir()
    resolved_parent = parent.resolve(strict=True)
    if not resolved_parent.is_relative_to(repository):
        raise ValueError(f"managed path escapes repository: {relative}")
    return resolved_parent


def write_change(repository: Path, change: Change) -> None:
    relative = Path(change.path)
    parent = prepare_parent(repository, relative)
    target = parent / relative.name
    if target.is_symlink():
        raise ValueError(f"managed path must not be a symlink: {target}")
    if target.exists() and not target.is_file():
        raise ValueError(f"managed path is not a regular file: {target}")
    temporary = target.with_name(f".{target.name}.bluemap-addon-toolkit.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise ValueError(f"refusing to replace existing temporary file: {temporary}")
    try:
        with temporary.open("xb") as output:
            output.write(change.content)
        if target.exists():
            mode = target.lstat().st_mode
            if not stat.S_ISREG(mode):
                raise ValueError(f"managed path is not a regular file: {target}")
            os.chmod(temporary, stat.S_IMODE(mode))
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def migrate_repository(repository: Path, *, write: bool) -> list[Change]:
    repository = repository.resolve()
    if write and git_status(repository):
        raise ValueError(f"refusing dirty repository: {repository}")
    pending = differences(repository, planned_changes(repository))
    if write:
        for change in pending:
            write_change(repository, change)
    return pending
