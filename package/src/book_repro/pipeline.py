"""Safe P2 reproduction pipeline."""

from __future__ import annotations

import hashlib
import io
import json
import platform
import os
import shutil
import sys
import time
import traceback
import unittest
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import load_configuration, package_root
from .generation import generate_outputs
from .independent import run_independent_checks
from .offline import offline_active, offline_requested
from .production_adapter import write_production_observations
from .verification import sha256, verify_results


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tree_hash(root: Path, relative_files: list[Path]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(relative_files, key=lambda path: path.as_posix()):
        path = root / relative
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def source_tree_hash(root: Path) -> str:
    files = [
        path.relative_to(root)
        for base in (
            root / "src", root / "config", root / "tests", root / "docs",
            root / "assets", root / "locks", root / "provenance", root / ".github",
            root / "scripts",
        )
        if base.exists()
        for path in base.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    files.extend(
        relative for relative in (
            Path("pyproject.toml"), Path("README.md"), Path("Dockerfile"),
            Path(".dockerignore"), Path("bootstrap_windows.ps1"), Path("CITATION.cff"),
            Path("THIRD_PARTY_NOTICES.md"), Path("LICENSE_STATUS.md"), Path("CHANGELOG.md"),
            Path("RECEIVER_GUIDE_ES.md"),
        )
        if (root / relative).is_file()
    )
    return _tree_hash(root, files)


def run_tests(root: Path) -> dict:
    start = time.perf_counter()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {
        "status": "passed" if result.wasSuccessful() else "failed",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "seconds": time.perf_counter() - start,
        "log": stream.getvalue(),
    }


def environment_report(root: Path | None = None) -> dict:
    root = (root or package_root()).resolve()
    try:
        import reportlab
        reportlab_version = reportlab.Version
    except Exception as error:  # pragma: no cover - used for installation diagnostics
        reportlab_version = None
        reportlab_error = repr(error)
    else:
        reportlab_error = None
    python_ok = sys.version_info[:2] == (3, 12)
    reportlab_ok = reportlab_version == "4.4.9"
    configuration_ok = True
    configuration_error = None
    try:
        load_configuration(root)
    except Exception as error:
        configuration_ok = False
        configuration_error = repr(error)
    latexmk = shutil.which("latexmk")
    pdflatex = shutil.which("pdflatex")
    pdfinfo = shutil.which("pdfinfo")
    pdftoppm = shutil.which("pdftoppm")
    documentation_status = "available" if latexmk and pdflatex else "unavailable"
    return {
        "status": "passed" if python_ok and reportlab_ok and configuration_ok else "failed",
        "package_version": __version__,
        "package_root": str(root),
        "python": sys.version,
        "python_executable": sys.executable,
        "python_required": ">=3.12,<3.13",
        "python_ok": python_ok,
        "reportlab": reportlab_version,
        "reportlab_required": "==4.4.9",
        "reportlab_ok": reportlab_ok,
        "reportlab_error": reportlab_error,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "configuration_ok": configuration_ok,
        "configuration_error": configuration_error,
        "calculation_network_required": False,
        "offline_execution": {
            "requested": offline_requested(),
            "python_socket_guard_active": offline_active(),
            "container_network_mode": os.environ.get("BOOK_REPRO_CONTAINER_NETWORK", "host_or_unspecified"),
        },
        "container": {
            "active": os.environ.get("BOOK_REPRO_CONTAINER") == "1",
            "image_role": os.environ.get("BOOK_REPRO_IMAGE_ROLE", "host"),
            "base_digest": os.environ.get("BOOK_REPRO_BASE_DIGEST"),
        },
        "documentation_toolchain": {
            "status": documentation_status,
            "latexmk": latexmk,
            "pdflatex": pdflatex,
            "pdfinfo": pdfinfo,
            "pdftoppm": pdftoppm,
            "note": "Calculation does not require TeX; build-docs requires latexmk and pdflatex.",
        },
        "docker": "active" if os.environ.get("BOOK_REPRO_CONTAINER") == "1" else "host_not_container",
    }


def reproduce(destination: Path, root: Path | None = None, command: str | None = None) -> dict:
    root = (root or package_root()).resolve()
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"Run destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    start_wall = time.perf_counter()
    started = _utc_now()
    report: dict = {
        "run_schema_version": 2,
        "status": "in_progress",
        "started_utc": started,
        "command": command,
        "package_version": __version__,
        "manuscript_version": "v22",
        "parameter_set_id": "synthetic-benchmark-v4",
        "source_tree_sha256": source_tree_hash(root),
        "stages": {},
    }
    try:
        environment = environment_report(root)
        report["stages"]["check_env"] = environment
        if environment["status"] != "passed":
            raise RuntimeError("Environment check failed.")
        tests = run_tests(root)
        report["stages"]["tests"] = tests
        if tests["status"] != "passed":
            raise RuntimeError("Mandatory tests failed before calculation.")
        parameters, policies, settings = load_configuration(root)
        report["configuration_files"] = settings["configuration_files"]
        archived_config = destination / "inputs" / "config"
        archived_config.mkdir(parents=True)
        for name in sorted(settings["configuration_files"]):
            shutil.copy2(root / "config" / name, archived_config / name)
        calculation_start = time.perf_counter()
        summary = generate_outputs(
            destination,
            root,
            parameters,
            policies,
            settings,
            {
                "run_schema_version": 2,
                "package_version": __version__,
                "manuscript_version": settings["package"]["manuscript_version"],
                "parameter_set_id": settings["package"]["parameter_set_id"],
                "source_tree_sha256": report["source_tree_sha256"],
                "configuration_files": settings["configuration_files"],
            },
        )
        report["stages"]["calculation"] = {
            "status": "passed",
            "seconds": time.perf_counter() - calculation_start,
            "summary": summary,
        }
        observation_start = time.perf_counter()
        observation_path = write_production_observations(destination, parameters, policies)
        report["stages"]["production_observation_adapter"] = {
            "status": "passed",
            "seconds": time.perf_counter() - observation_start,
            "output": str(observation_path.relative_to(destination)).replace("\\", "/"),
            "scope": "observed side for P3 edge-case comparisons",
        }
        oracle_start = time.perf_counter()
        independent = run_independent_checks(root, destination)
        independent_path = destination / "independent" / "oracle_results.json"
        independent_path.parent.mkdir(parents=True, exist_ok=True)
        independent_path.write_text(
            json.dumps(independent, indent=2, sort_keys=True), encoding="utf-8"
        )
        report["stages"]["independent_oracles"] = {
            "status": independent["status"],
            "seconds": time.perf_counter() - oracle_start,
            "groups_total": independent["groups_total"],
            "groups_failed": independent["groups_failed"],
            "configurations_checked": independent["configurations_checked"],
            "heterogeneous_units_total": independent["heterogeneous_units_total"],
            "count_notice": independent["count_notice"],
            "coverage_counts_by_unit": independent["coverage_counts_by_unit"],
            "scope": "exact Appendix A oracles and finite Chapter 16 complements",
        }
        if independent["status"] != "passed":
            raise AssertionError("Independent oracle stage failed.")
        verification = verify_results(
            root,
            destination,
            expected_identity={
                "package_version": settings["package"]["package_version"],
                "manuscript_version": settings["package"]["manuscript_version"],
                "parameter_set_id": settings["package"]["parameter_set_id"],
                "source_tree_sha256": report["source_tree_sha256"],
            },
        )
        verification["pending"]["independent_oracles_P3"] = "passed_separate_stage"
        (destination / "verification.json").write_text(
            json.dumps(verification, indent=2, sort_keys=True), encoding="utf-8"
        )
        report["stages"]["verification"] = {
            "status": verification["status"],
            "checks_total": verification["checks_total"],
            "physical_output_files": verification["physical_output_files"],
            "checks_failed": verification["checks_failed"],
        }
        if verification["status"] != "passed":
            raise AssertionError("Written-file verification failed.")
        report["stages"]["editorial_controls"] = {"status": "not_run", "scheduled": "P4"}
        report["status"] = "passed"
        report["finished_utc"] = _utc_now()
        report["seconds"] = time.perf_counter() - start_wall
        produced = [path for path in destination.rglob("*") if path.is_file()]
        report["produced_files"] = {
            str(path.relative_to(destination)).replace("\\", "/"): sha256(path)
            for path in sorted(produced)
            if path.name not in {"run_report.json", "COMPLETE.json"}
        }
        (destination / "run_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        complete = {
            "schema_version": 2,
            "status": "passed",
            "run_report_sha256": sha256(destination / "run_report.json"),
            "completed_utc": report["finished_utc"],
        }
        (destination / "COMPLETE.json").write_text(
            json.dumps(complete, indent=2, sort_keys=True), encoding="utf-8"
        )
        return report
    except Exception as error:
        report["status"] = "failed"
        report["finished_utc"] = _utc_now()
        report["seconds"] = time.perf_counter() - start_wall
        report["error"] = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
        (destination / "run_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        raise
