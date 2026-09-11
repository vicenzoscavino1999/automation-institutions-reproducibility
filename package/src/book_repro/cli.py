"""Command-line interface for the reproducibility package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .comparison import compare_runs
from .config import package_root
from .coverage import coverage_report
from .editorial import build_docs
from .manuscript import check_book
from .offline import activate_offline_guard, restore_offline_guard
from .packaging import assemble_distribution, verify_distribution_archive
from .pipeline import environment_report, reproduce, run_tests
from .verification import verify_run


def _print(value: dict) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="python -m book_repro")
    subparsers = result.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-env", help="Inspect the calculation environment.")
    reproduce_parser = subparsers.add_parser("reproduce", help="Recompute and verify a new run.")
    reproduce_parser.add_argument("--output", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify", help="Verify files already written by a run.")
    verify_parser.add_argument("--run", type=Path, required=True)
    docs_parser = subparsers.add_parser(
        "build-docs", help="Build a standalone document from a verified current run."
    )
    docs_parser.add_argument("--run", type=Path, required=True)
    docs_parser.add_argument("--output", type=Path)
    book_parser = subparsers.add_parser(
        "check-book", help="Check registered claims in an identified manuscript copy."
    )
    book_parser.add_argument("--manuscript", type=Path, required=True)
    book_parser.add_argument("--run", type=Path, required=True)
    book_parser.add_argument("--output", type=Path)
    subparsers.add_parser("test", help="Run the currently implemented test suite.")
    compare_parser = subparsers.add_parser(
        "compare-runs", help="Compare Windows, Linux and baseline scientific outputs."
    )
    compare_parser.add_argument("--windows", type=Path, required=True)
    compare_parser.add_argument("--linux", type=Path, required=True)
    compare_parser.add_argument("--baseline", type=Path)
    compare_parser.add_argument("--output", type=Path)
    coverage_parser = subparsers.add_parser(
        "coverage", help="Validate the whole-book coverage registry."
    )
    coverage_parser.add_argument("--output", type=Path)
    coverage_parser.add_argument(
        "--manuscript",
        type=Path,
        help=(
            "Optionally validate labels and locators against the identified v22. "
            "Without it, the check is structural and package-only."
        ),
    )
    package_parser = subparsers.add_parser(
        "package", help="Assemble the allowlisted local distribution ZIP."
    )
    package_parser.add_argument("--run", type=Path, required=True)
    package_parser.add_argument("--document", type=Path, required=True)
    package_parser.add_argument("--output", type=Path, required=True)
    package_verify_parser = subparsers.add_parser(
        "verify-package", help="Verify the assembled ZIP and all embedded checksums."
    )
    package_verify_parser.add_argument("--archive", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    root = package_root()
    guard_token = activate_offline_guard()
    try:
        if arguments.command == "check-env":
            report = environment_report(root)
            _print(report)
            return 0 if report["status"] == "passed" else 1
        if arguments.command == "reproduce":
            command = " ".join(sys.argv)
            report = reproduce(arguments.output, root, command)
            _print(report)
            return 0
        if arguments.command == "verify":
            report = verify_run(root, arguments.run.resolve())
            _print(report)
            return 0 if report["status"] == "passed" else 1
        if arguments.command == "build-docs":
            output = arguments.output or root / "build" / f"docs-{arguments.run.name}"
            report = build_docs(root, arguments.run, output)
            _print(report)
            return 0 if report["status"] == "passed" else 1
        if arguments.command == "check-book":
            report = check_book(root, arguments.manuscript, arguments.run, arguments.output)
            _print(report)
            return 0 if report["status"] == "passed" else 1
        if arguments.command == "test":
            report = run_tests(root)
            _print(report)
            return 0 if report["status"] == "passed" else 1
        if arguments.command == "compare-runs":
            report = compare_runs(
                root, arguments.windows, arguments.linux, arguments.baseline, arguments.output
            )
            _print(report)
            return 0 if report["status"] == "passed" else 1
        if arguments.command == "coverage":
            report = coverage_report(root, arguments.output, arguments.manuscript)
            _print(report)
            return 0 if report["status"] == "passed" else 1
        if arguments.command == "package":
            report = assemble_distribution(
                root, arguments.run, arguments.document, arguments.output
            )
            _print(report)
            return 0 if report["status"] == "passed" else 1
        if arguments.command == "verify-package":
            report = verify_distribution_archive(arguments.archive)
            _print(report)
            return 0 if report["status"] == "passed" else 1
    except Exception as error:
        print(json.dumps({"status": "failed", "error": type(error).__name__, "message": str(error)}, indent=2), file=sys.stderr)
        return 1
    finally:
        restore_offline_guard(guard_token)
    return 2
