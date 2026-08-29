"""Command-line interface for BlueMap Add-on Toolkit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence
import zipfile

from . import artifacts, contract, migration, staging
from .version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bluemap-addon-toolkit",
        description="Development and release checks for independent BlueMap add-ons.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    conventions = commands.add_parser(
        "conventions", help="check or migrate the addon-v1 repository contract"
    )
    convention_commands = conventions.add_subparsers(
        dest="conventions_command", required=True
    )
    convention_check = convention_commands.add_parser("check")
    convention_check.add_argument("repositories", nargs="+", type=Path)
    convention_check.add_argument(
        "--json", action="store_true", help="emit machine-readable results"
    )
    convention_migrate = convention_commands.add_parser("migrate")
    convention_migrate.add_argument("repositories", nargs="+", type=Path)
    convention_mode = convention_migrate.add_mutually_exclusive_group(required=True)
    convention_mode.add_argument("--check", action="store_true")
    convention_mode.add_argument("--dry-run", action="store_true")
    convention_mode.add_argument("--write", action="store_true")

    artifact_parser = commands.add_parser(
        "artifacts", help="verify exact candidate artifacts"
    )
    artifact_commands = artifact_parser.add_subparsers(
        dest="artifacts_command", required=True
    )
    artifact_verify = artifact_commands.add_parser("verify")
    artifact_verify.add_argument("--manifest", type=Path, required=True)
    artifact_verify.add_argument("--artifact", action="append", default=[])

    entries_parser = commands.add_parser(
        "jar-entries", help="write or verify accepted non-manifest JAR entries"
    )
    entries_commands = entries_parser.add_subparsers(
        dest="jar_entries_command", required=True
    )
    entries_write = entries_commands.add_parser("write")
    entries_write.add_argument("--jar", type=Path, required=True)
    entries_write.add_argument("--entries", type=Path, required=True)
    entries_verify = entries_commands.add_parser("verify")
    entries_verify.add_argument("--jar", type=Path, required=True)
    entries_verify.add_argument("--entries", type=Path, required=True)
    entries_verify.add_argument("--expected-version", required=True)
    return parser


def run_conventions(args: argparse.Namespace) -> int:
    if args.conventions_command == "check":
        results = [contract.check_repository(path) for path in args.repositories]
        sys.stdout.write(contract.format_results(results, as_json=args.json))
        return 0 if all(bool(result["ok"]) for result in results) else 1

    stale = False
    try:
        for raw in args.repositories:
            repository = raw.resolve()
            pending = migration.migrate_repository(repository, write=args.write)
            stale = stale or bool(pending)
            state = "current" if not pending else "would update"
            if args.write and pending:
                state = "updated"
            print(f"{state} {repository}")
            for change in pending:
                print(f"  {change.path}")
    except (OSError, RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    return 1 if args.check and stale else 0


def run_artifacts(args: argparse.Namespace) -> int:
    try:
        for message in artifacts.verify_artifacts(args.manifest, args.artifact):
            print(message)
        return 0
    except (json.JSONDecodeError, OSError, UnicodeError, ValueError, zipfile.BadZipFile) as error:
        print(f"artifact verification failed: {error}", file=sys.stderr)
        return 1


def run_jar_entries(args: argparse.Namespace) -> int:
    try:
        if args.jar_entries_command == "write":
            print(staging.write_entries(args.jar, args.entries))
        else:
            print(
                staging.verify_entries(
                    args.jar,
                    args.entries,
                    args.expected_version,
                )
            )
        return 0
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile) as error:
        print(f"staged equivalence failed: {error}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "conventions":
        return run_conventions(args)
    if args.command == "artifacts":
        return run_artifacts(args)
    if args.command == "jar-entries":
        return run_jar_entries(args)
    raise AssertionError(f"unhandled command: {args.command}")
