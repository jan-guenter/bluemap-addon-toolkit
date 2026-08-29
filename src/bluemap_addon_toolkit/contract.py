"""Validation for the versioned BlueMap add-on repository contract."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Iterable


ACTION_USE = re.compile(r"(?m)^\s*(?:-\s*)?uses:\s*([^\s#]+)")
FULL_COMMIT = re.compile(r"[0-9a-fA-F]{40}")
PROPERTY = re.compile(r"(?m)^([A-Za-z][A-Za-z0-9_.-]*)\s*=\s*(.*?)\s*$")

REQUIRED_PATHS = (
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "CHANGELOG.md",
    "LICENSE",
    "NOTICE.md",
    "README.md",
    "THIRD_PARTY.md",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    "build.gradle",
    "config/checkstyle/checkstyle.xml",
    "docs/RELEASING.md",
    "gallery/README.md",
    "gradle.properties",
    "provenance/upstreams.json",
    "settings.gradle",
    "src/main/resources/bluemap.addon.json",
)

REQUIRED_PROPERTIES = (
    "addon_group",
    "addon_id",
    "addon_name",
    "addon_version",
    "artifact_id",
    "bluemap_version",
    "org.gradle.configuration-cache",
    "org.gradle.daemon",
    "org.gradle.jvmargs",
)

STANDARD_FILES = {
    ".editorconfig": "editorconfig",
    ".gitattributes": "gitattributes",
    "config/checkstyle/checkstyle.xml": "checkstyle.xml",
}


@dataclass(frozen=True)
class Finding:
    """One contract violation."""

    path: str
    message: str


def standard_bytes(name: str) -> bytes:
    """Read a packaged addon-v1 standard file."""

    return files("bluemap_addon_toolkit").joinpath("data", "addon-v1", name).read_bytes()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def tracked_files(repository: Path, pattern: str) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repository), "ls-files", "-z", pattern],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        detail = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(detail or f"could not enumerate {repository}")
    return [repository / item.decode() for item in result.stdout.split(b"\0") if item]


def compare_standard(repository: Path, local: str, standard: str) -> list[Finding]:
    target = repository / local
    if regular_file(target) and target.read_bytes() != standard_bytes(standard):
        return [Finding(local, f"must match addon-v1/{standard}")]
    return []


def check_workflow(repository: Path, relative: str) -> list[Finding]:
    path = repository / relative
    if not regular_file(path):
        return []
    findings: list[Finding] = []
    for value in ACTION_USE.findall(read(path)):
        if value.startswith("./"):
            continue
        revision = value.rsplit("@", 1)[-1] if "@" in value else ""
        if not FULL_COMMIT.fullmatch(revision):
            findings.append(
                Finding(relative, f"action is not pinned to a full commit: {value}")
            )
    return findings


def check_java(repository: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in tracked_files(repository, "*.java"):
        relative = path.relative_to(repository).as_posix()
        if path.is_symlink() or not path.is_file():
            findings.append(Finding(relative, "Java source must be a regular file"))
            continue
        data = path.read_bytes()
        if b"\r" in data:
            findings.append(Finding(relative, "Java source must use LF line endings"))
        if b"\t" in data:
            findings.append(Finding(relative, "Java source must not contain tabs"))
        if data and not data.endswith(b"\n"):
            findings.append(Finding(relative, "Java source needs a final newline"))
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(Finding(relative, "Java source is not UTF-8"))
            continue
        if re.search(r"(?m)[ \t]+$", text):
            findings.append(Finding(relative, "Java source has trailing whitespace"))
        package = re.search(r"(?m)^package\s+([^;]+);", text)
        if (
            relative.startswith("src/main/java/")
            and package
            and not package.group(1).startswith("io.github.janguenter.bluemap.")
        ):
            findings.append(
                Finding(
                    relative,
                    "Java package is outside io.github.janguenter.bluemap",
                )
            )
    return findings


def check_repository(repository: Path) -> dict[str, object]:
    """Return a stable machine-readable addon-v1 result."""

    repository = repository.resolve()
    findings: list[Finding] = []
    is_git = (repository / ".git").exists()
    if not is_git:
        findings.append(Finding(".", "not a Git worktree"))

    for relative in REQUIRED_PATHS:
        if not regular_file(repository / relative):
            findings.append(Finding(relative, "required file is missing"))

    for local, standard in STANDARD_FILES.items():
        findings.extend(compare_standard(repository, local, standard))

    properties_path = repository / "gradle.properties"
    if regular_file(properties_path):
        properties = dict(PROPERTY.findall(read(properties_path)))
        for key in REQUIRED_PROPERTIES:
            if not properties.get(key):
                findings.append(Finding("gradle.properties", f"missing property {key}"))

    build_path = repository / "build.gradle"
    if regular_file(build_path):
        build = read(build_path)
        checks = (
            (r"id\s+['\"]java-library['\"]", "java-library plugin is missing"),
            (r"id\s+['\"]checkstyle['\"]", "checkstyle plugin is missing"),
            (r"id\s+['\"]maven-publish['\"]", "maven-publish plugin is missing"),
            (r"JavaLanguageVersion\.of\(21\)", "Java 21 toolchain is missing"),
            (r"options\.release\s*=\s*21", "Java release 21 is missing"),
            (r"options\.encoding\s*=\s*['\"]UTF-8['\"]", "UTF-8 compilation is missing"),
            (r"-Xlint:all", "-Xlint:all compilation is missing"),
            (r"-Werror", "-Werror compilation is missing"),
            (r"toolVersion\s*=\s*['\"]10\.18\.2['\"]", "Checkstyle 10.18.2 is missing"),
            (r"preserveFileTimestamps\s*=\s*false", "timestamp-free archives are missing"),
            (r"reproducibleFileOrder\s*=\s*true", "reproducible archive order is missing"),
        )
        for pattern, message in checks:
            if not re.search(pattern, build):
                findings.append(Finding("build.gradle", message))

    findings.extend(check_workflow(repository, ".github/workflows/ci.yml"))
    findings.extend(check_workflow(repository, ".github/workflows/release.yml"))
    if is_git:
        try:
            findings.extend(check_java(repository))
        except RuntimeError as error:
            findings.append(Finding(".", str(error)))

    ordered = sorted(findings, key=lambda item: (item.path, item.message))
    return {
        "repository": str(repository),
        "contract": "addon-v1",
        "ok": not ordered,
        "findings": [asdict(item) for item in ordered],
    }


def format_results(results: Iterable[dict[str, object]], *, as_json: bool) -> str:
    collected = list(results)
    if as_json:
        return json.dumps(collected, indent=2, sort_keys=True) + "\n"
    lines: list[str] = []
    for result in collected:
        state = "PASS" if result["ok"] else "FAIL"
        lines.append(f"{state} {result['repository']}")
        for finding in result["findings"]:  # type: ignore[union-attr]
            lines.append(f"  {finding['path']}: {finding['message']}")
    passed = sum(bool(result["ok"]) for result in collected)
    lines.append(f"{passed}/{len(collected)} repositories satisfy addon-v1")
    return "\n".join(lines) + "\n"
