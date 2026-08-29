#!/usr/bin/env python3
"""Build, audit, and exercise the Gradle convention plugin."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "gradle"
SUPPORTED = {"9.4.0", "9.6.1"}


def toolkit_version() -> str:
    source = (ROOT / "src/bluemap_addon_toolkit/version.py").read_text(
        encoding="utf-8"
    )
    matches = re.findall(r'^__version__ = "([^"]+)"$', source, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError("could not read the unique toolkit version")
    return matches[0]


def run(gradle: str, project: Path, *tasks: str, environment: dict[str, str]) -> None:
    subprocess.run(
        [
            gradle,
            "--no-daemon",
            "--stacktrace",
            "--warning-mode",
            "fail",
            "-p",
            str(project),
            *tasks,
        ],
        check=True,
        cwd=ROOT,
        env=environment,
    )


def gradle_version(gradle: str, environment: dict[str, str]) -> str:
    result = subprocess.run(
        [gradle, "--version"],
        check=True,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
    )
    match = re.search(r"^Gradle ([^\s]+)$", result.stdout, re.MULTILINE)
    if match is None:
        raise ValueError("could not read Gradle version")
    return match.group(1)


def artifact_bytes(project: Path, relative_paths: tuple[str, ...]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for relative in relative_paths:
        candidate = project / relative
        if not candidate.is_file():
            raise ValueError(f"expected Gradle artifact is missing: {candidate}")
        result[relative] = candidate.read_bytes()
    return result


def resolve_gradle(value: str) -> str:
    if "/" not in value and "\\" not in value:
        resolved = shutil.which(value)
        if resolved is None:
            raise ValueError(f"Gradle executable not found on PATH: {value}")
        return str(Path(resolved).resolve(strict=True))

    candidate = Path(value).expanduser().resolve(strict=True)
    if not candidate.is_file():
        raise ValueError(f"Gradle executable is not a file: {candidate}")
    if os.name != "nt" and not os.access(candidate, os.X_OK):
        raise ValueError(f"Gradle executable is not executable: {candidate}")
    return str(candidate)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gradle", default="gradle")
    args = parser.parse_args()
    gradle = resolve_gradle(args.gradle)

    with tempfile.TemporaryDirectory(prefix="bluemap-toolkit-gradle-") as temporary:
        environment = os.environ.copy()
        environment["GRADLE_USER_HOME"] = str(Path(temporary) / "gradle-user-home")
        selected_gradle = gradle_version(gradle, environment)
        if selected_gradle not in SUPPORTED:
            raise ValueError(
                f"Gradle {selected_gradle} is outside the tested set: {sorted(SUPPORTED)}"
            )

        release_version = toolkit_version()
        plugin_outputs = (
            f"build/libs/bluemap-addon-toolkit-gradle-{release_version}.jar",
            f"build/libs/bluemap-addon-toolkit-gradle-{release_version}-sources.jar",
        )
        run(gradle, PLUGIN, "clean", "check", "sourcesJar", environment=environment)
        first = artifact_bytes(PLUGIN, plugin_outputs)
        run(gradle, PLUGIN, "clean", "check", "sourcesJar", environment=environment)
        second = artifact_bytes(PLUGIN, plugin_outputs)
        if first != second:
            raise ValueError(
                f"Gradle {selected_gradle} produced non-reproducible plugin archives"
            )

        fixture = PLUGIN / "fixtures" / "java-checkstyle"
        run(
            gradle,
            fixture,
            "clean",
            "verifyConventions",
            environment=environment,
        )
        fixture_outputs = (
            "build/libs/fixture-addon-1.2.3.jar",
            "build/libs/fixture-addon-1.2.3-sources.jar",
            "build/publications/addon/pom-default.xml",
            "build/publications/addon/module.json",
        )
        fixture_first = artifact_bytes(fixture, fixture_outputs)
        run(gradle, fixture, "clean", "verifyConventions", environment=environment)
        fixture_second = artifact_bytes(fixture, fixture_outputs)
        if fixture_first != fixture_second:
            raise ValueError(
                f"Gradle {selected_gradle} produced non-reproducible consumer artifacts"
            )
        run(
            gradle,
            PLUGIN / "fixtures" / "no-core-plugins",
            "verifyConventions",
            environment=environment,
        )
        print(f"Gradle {selected_gradle} convention plugin checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
