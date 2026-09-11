"""Verify generated outputs and the traceability chain of sealed runs."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .config import load_tolerances


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().lower()


def normalized_text_sha256(path: Path) -> str:
    """Hash UTF-8 text after normalizing only platform line endings.

    Frozen reference bytes remain protected by their ordinary SHA-256.  This
    second digest is used only when comparing generated text across Windows
    and Linux, where Python and third-party writers may select CRLF or LF.
    """
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tree_hash(root: Path) -> str:
    relative_files = [
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
    relative_files.extend(
        relative for relative in (
            Path("pyproject.toml"), Path("README.md"), Path("Dockerfile"),
            Path(".dockerignore"), Path("bootstrap_windows.ps1"), Path("CITATION.cff"),
            Path("THIRD_PARTY_NOTICES.md"), Path("LICENSE_STATUS.md"), Path("CHANGELOG.md"),
            Path("RECEIVER_GUIDE_ES.md"),
        )
        if (root / relative).is_file()
    )
    digest = hashlib.sha256()
    for relative in sorted(relative_files, key=lambda value: value.as_posix()):
        path = root / relative
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _json_object(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not path.is_file():
        return None, [{"kind": "missing_file", "path": str(path)}]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, [{"kind": "invalid_json", "path": str(path), "detail": repr(error)}]
    if not isinstance(value, dict):
        return None, [{"kind": "json_root_type", "path": str(path), "expected": "object"}]
    return value, []


def _read_csv(
    path: Path, side: str
) -> tuple[list[str], list[dict[str, str]], list[dict[str, Any]]]:
    """Read a CSV without allowing DictReader to hide short or long rows."""
    issues: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            columns = next(reader)
        except StopIteration:
            return [], [], [{"kind": "csv_missing_header", "side": side}]
        normalized = [column.strip() for column in columns]
        if not columns or any(not column for column in normalized):
            issues.append({"kind": "csv_ambiguous_header", "side": side, "detail": "empty column name"})
        duplicates = sorted({column for column in normalized if normalized.count(column) > 1})
        if duplicates:
            issues.append({
                "kind": "csv_ambiguous_header",
                "side": side,
                "detail": "duplicate column names after trimming",
                "columns": duplicates,
            })
        rows: list[dict[str, str]] = []
        for row_number, values in enumerate(reader, start=2):
            if len(values) != len(columns):
                issues.append({
                    "kind": "csv_row_length",
                    "side": side,
                    "row_number": row_number,
                    "expected_cells": len(columns),
                    "observed_cells": len(values),
                    "direction": "extra" if len(values) > len(columns) else "missing",
                })
                continue
            # Empty strings remain present values; only a physically short row
            # is a missing field.
            rows.append(dict(zip(columns, values, strict=True)))
    return columns, rows, issues


def _key(row: dict[str, str], columns: list[str]) -> tuple[str, ...]:
    return tuple(row[column] for column in columns)


def _finite_number(value: str) -> float | None:
    if value == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    if not math.isfinite(number):
        raise ValueError(f"Unexpected non-finite numeric value: {value}")
    return number


def _compare_csv(
    generated: Path,
    reference: Path,
    keys: list[str],
    atol: float,
    rtol: float,
) -> dict[str, Any]:
    generated_columns, generated_rows, generated_issues = _read_csv(generated, "generated")
    reference_columns, reference_rows, reference_issues = _read_csv(reference, "reference")
    issues: list[dict[str, Any]] = [*generated_issues, *reference_issues]
    if issues:
        return {"status": "failed", "issues": issues[:50], "issue_count": len(issues)}
    if generated_columns != reference_columns:
        issues.append({"kind": "columns", "expected": reference_columns, "observed": generated_columns})
        return {"status": "failed", "issues": issues, "issue_count": len(issues)}
    for column in keys:
        if column not in generated_columns:
            issues.append({"kind": "missing_key_column", "column": column})
    if issues:
        return {"status": "failed", "issues": issues, "issue_count": len(issues)}
    generated_map: dict[tuple[str, ...], dict[str, str]] = {}
    reference_map: dict[tuple[str, ...], dict[str, str]] = {}
    for label, rows, target in (
        ("generated", generated_rows, generated_map),
        ("reference", reference_rows, reference_map),
    ):
        for row in rows:
            row_key = _key(row, keys)
            if row_key in target:
                issues.append({"kind": "duplicate_key", "side": label, "key": row_key})
            target[row_key] = row
    missing = sorted(set(reference_map) - set(generated_map))
    extra = sorted(set(generated_map) - set(reference_map))
    if missing:
        issues.append({"kind": "missing_rows", "count": len(missing), "sample": missing[:5]})
    if extra:
        issues.append({"kind": "extra_rows", "count": len(extra), "sample": extra[:5]})
    compared_cells = 0
    for row_key in sorted(set(reference_map) & set(generated_map)):
        expected = reference_map[row_key]
        observed = generated_map[row_key]
        for column in generated_columns:
            compared_cells += 1
            left = expected[column]
            right = observed[column]
            try:
                left_number = _finite_number(left)
                right_number = _finite_number(right)
            except ValueError as error:
                issues.append({"kind": "nonfinite", "key": row_key, "column": column, "detail": str(error)})
                continue
            if left_number is not None and right_number is not None:
                limit = atol + rtol * abs(left_number)
                if abs(right_number - left_number) > limit:
                    issues.append({
                        "kind": "numeric_value",
                        "key": row_key,
                        "column": column,
                        "expected": left_number,
                        "observed": right_number,
                        "tolerance": limit,
                    })
            elif left != right:
                issues.append({
                    "kind": "exact_value",
                    "key": row_key,
                    "column": column,
                    "expected": left,
                    "observed": right,
                })
    return {
        "status": "passed" if not issues else "failed",
        "rows": len(generated_rows),
        "columns": len(generated_columns),
        "compared_cells": compared_cells,
        "issues": issues[:50],
        "issue_count": len(issues),
    }


def _identity_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_version": manifest["package_version"],
        "manuscript_version": manifest["manuscript_version"],
        "parameter_set_id": manifest["parameter_set_id"],
    }


def verify_results(
    package_root: Path,
    run_root: Path,
    *,
    expected_identity: dict[str, Any] | None = None,
    allow_legacy_metadata: bool = False,
) -> dict[str, Any]:
    """Verify outputs while a reproduction is still open.

    This function intentionally does not require ``run_report.json`` or
    ``COMPLETE.json``. It is the non-circular check used by ``reproduce``
    before sealing the run.
    """
    package_root = package_root.resolve()
    run_root = run_root.resolve()
    manifest_path = package_root / "reference" / "manifest.json"
    tolerances = load_tolerances(package_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for item in manifest["files"]:
        generated = run_root / item["generated_path"]
        reference = package_root / item["reference_path"]
        check: dict[str, Any] = {
            "id": item["id"],
            "generated_path": item["generated_path"],
            "type": item["type"],
        }
        if not reference.is_file():
            check.update(status="failed", issues=[{"kind": "missing_reference_file"}])
        elif sha256(reference) != item["reference_sha256"]:
            check.update(status="failed", issues=[{"kind": "reference_hash_mismatch"}])
        elif not generated.is_file():
            check.update(status="failed", issues=[{"kind": "missing_generated_file"}])
        elif item["type"] == "csv":
            check.update(_compare_csv(
                generated,
                reference,
                item["keys"],
                tolerances["atol"],
                tolerances["rtol"],
            ))
        elif item["type"] in {"text", "svg"}:
            expected_normalized = normalized_text_sha256(reference)
            observed_normalized = normalized_text_sha256(generated)
            check.update(
                status="passed" if observed_normalized == expected_normalized else "failed",
                observed_sha256=sha256(generated),
                reference_normalized_sha256=expected_normalized,
                observed_normalized_sha256=observed_normalized,
                comparison_policy="exact_utf8_text_after_line_ending_normalization",
                issues=[] if observed_normalized == expected_normalized else [
                    {"kind": "hash_mismatch", "comparison": "normalized_utf8_text"}
                ],
            )
        elif item["type"] == "pdf_basic":
            prefix = generated.read_bytes()[:5]
            valid = prefix == b"%PDF-" and generated.stat().st_size > 100
            check.update(
                status="passed" if valid else "failed",
                bytes=generated.stat().st_size,
                issues=[] if valid else [{"kind": "invalid_pdf_container"}],
                editorial_equivalence="not_run",
            )
        else:
            check.update(status="failed", issues=[{"kind": "unknown_manifest_type"}])
        checks.append(check)
        if check["status"] != "passed":
            failures.append(check)

    metadata_path = run_root / "results" / "run_metadata.json"
    metadata_check: dict[str, Any] = {
        "id": "generated_run_metadata",
        "generated_path": "results/run_metadata.json",
        "type": "generated_json",
        "issues": [],
        "warnings": [],
    }
    metadata, metadata_errors = _json_object(metadata_path)
    metadata_check["issues"].extend(metadata_errors)
    if metadata is not None:
        required = {
            "package_version", "manuscript_version", "parameter_set_id",
            "source_tree_sha256", "configuration_files",
        }
        for field in sorted(required - set(metadata)):
            metadata_check["issues"].append({"kind": "metadata_missing_field", "field": field})
        identity = _identity_from_manifest(manifest)
        current_package_path = package_root / "config" / "package.json"
        if current_package_path.is_file():
            current_package = json.loads(current_package_path.read_text(encoding="utf-8"))
            identity_fields = ("package_version", "manuscript_version", "parameter_set_id")
            if all(metadata.get(field) == current_package.get(field) for field in identity_fields):
                identity = {field: current_package[field] for field in identity_fields}
        if expected_identity:
            identity.update(expected_identity)
        for field, expected in identity.items():
            if metadata.get(field) != expected:
                metadata_check["issues"].append({
                    "kind": "metadata_identity",
                    "field": field,
                    "expected": expected,
                    "observed": metadata.get(field),
                })
        configuration_files = metadata.get("configuration_files")
        if not isinstance(configuration_files, dict):
            metadata_check["issues"].append({"kind": "metadata_configuration_files_type"})
        else:
            current_hashes = {
                name: sha256(package_root / "config" / name)
                for name in ("benchmark.json", "scenarios.json", "package.json", "tolerances.json")
            }
            required_names = set(current_hashes)
            if allow_legacy_metadata and "tolerances.json" not in configuration_files:
                required_names.remove("tolerances.json")
                metadata_check["warnings"].append({"kind": "legacy_tolerance_hash_absent"})
            for name in sorted(required_names):
                observed = configuration_files.get(name)
                if observed is None:
                    metadata_check["issues"].append({
                        "kind": "metadata_configuration_hash_missing", "file": name,
                    })
                elif expected_identity and observed != current_hashes[name]:
                    metadata_check["issues"].append({
                        "kind": "metadata_configuration_hash",
                        "file": name,
                        "expected": current_hashes[name],
                        "observed": observed,
                    })
    metadata_check["status"] = "passed" if not metadata_check["issues"] else "failed"
    checks.append(metadata_check)
    if metadata_check["status"] != "passed":
        failures.append(metadata_check)

    expected_generated = {item["generated_path"] for item in manifest["files"]}
    expected_generated.add("results/run_metadata.json")
    observed_generated = {
        str(path.relative_to(run_root)).replace("\\", "/")
        for directory in (run_root / "results", run_root / "figures")
        if directory.is_dir()
        for path in directory.rglob("*")
        if path.is_file()
    }
    unexpected = sorted(observed_generated - expected_generated)
    inventory_check: dict[str, Any] = {
        "id": "generated_file_inventory",
        "type": "inventory",
        "status": "passed" if not unexpected else "failed",
        "observed_files": len(observed_generated),
        "expected_files": len(expected_generated),
        "issues": [] if not unexpected else [{"kind": "unexpected_generated_files", "files": unexpected}],
    }
    checks.append(inventory_check)
    if inventory_check["status"] != "passed":
        failures.append(inventory_check)
    return {
        "status": "passed" if not failures else "failed",
        "verification_scope": "results_before_closure",
        "manifest": str(manifest_path),
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failures),
        "checks_failed": len(failures),
        "physical_output_files": len(expected_generated),
        "inventory_checks": 1,
        "checked_files": len(checks),
        "passed_files": len(checks) - len(failures),
        "failed_files": len(failures),
        "count_description": (
            f"{len(checks)} checks over {len(expected_generated)} result/figure files; "
            "the inventory check is not an additional physical file"
        ),
        "checks": checks,
        "pending": {
            "completed_run_traceability": "not_run_in_preclosure_check",
            "independent_oracles_P3": "not_run",
            "editorial_figure_equivalence_P4": "not_run",
            "book_correspondence_P4": "not_run",
            "clean_environments_and_CI_P5": "not_run",
        },
    }


def _trace_check(identifier: str, issues: list[dict[str, Any]], **details: Any) -> dict[str, Any]:
    return {
        "id": identifier,
        "type": "completed_run_traceability",
        "status": "passed" if not issues else "failed",
        "issues": issues,
        **details,
    }


def verify_run(package_root: Path, run_root: Path) -> dict[str, Any]:
    """Verify an already sealed run without modifying any file inside it."""
    package_root = package_root.resolve()
    run_root = run_root.resolve()
    metadata, _ = _json_object(run_root / "results" / "run_metadata.json")
    legacy = not isinstance(metadata, dict) or metadata.get("run_schema_version", 1) < 2
    archived_package, _ = _json_object(run_root / "inputs" / "config" / "package.json")
    run_identity = None
    if isinstance(archived_package, dict):
        required_identity = ("package_version", "manuscript_version", "parameter_set_id")
        if all(field in archived_package for field in required_identity):
            run_identity = {field: archived_package[field] for field in required_identity}
    results = verify_results(
        package_root,
        run_root,
        expected_identity=run_identity,
        allow_legacy_metadata=legacy,
    )
    trace_checks: list[dict[str, Any]] = []

    report, report_errors = _json_object(run_root / "run_report.json")
    complete, complete_errors = _json_object(run_root / "COMPLETE.json")
    document_issues = [*report_errors, *complete_errors]
    if report is not None:
        for field in (
            "status", "package_version", "manuscript_version", "parameter_set_id",
            "source_tree_sha256", "stages", "produced_files",
        ):
            if field not in report:
                document_issues.append({"kind": "run_report_missing_field", "field": field})
        if report.get("status") != "passed":
            document_issues.append({
                "kind": "run_report_status", "expected": "passed", "observed": report.get("status"),
            })
    if complete is not None:
        for field in ("status", "run_report_sha256", "completed_utc"):
            if field not in complete:
                document_issues.append({"kind": "complete_missing_field", "field": field})
        if complete.get("status") != "passed":
            document_issues.append({
                "kind": "complete_status", "expected": "passed", "observed": complete.get("status"),
            })
    trace_checks.append(_trace_check("sealed_documents", document_issues))

    link_issues: list[dict[str, Any]] = []
    if report is not None and complete is not None:
        observed_report_hash = sha256(run_root / "run_report.json")
        if complete.get("run_report_sha256") != observed_report_hash:
            link_issues.append({
                "kind": "completion_report_hash",
                "expected": observed_report_hash,
                "observed": complete.get("run_report_sha256"),
            })
    trace_checks.append(_trace_check("completion_link", link_issues))

    coherence_issues: list[dict[str, Any]] = []
    coherence_warnings: list[dict[str, Any]] = []
    if report is not None and metadata is not None:
        for field in ("package_version", "manuscript_version", "parameter_set_id", "source_tree_sha256"):
            if report.get(field) != metadata.get(field):
                coherence_issues.append({
                    "kind": "report_metadata_mismatch",
                    "field": field,
                    "report": report.get(field),
                    "metadata": metadata.get(field),
                })
        report_config = report.get("configuration_files")
        metadata_config = metadata.get("configuration_files")
        if report_config is None and legacy:
            coherence_warnings.append({"kind": "legacy_report_configuration_hashes_absent"})
        elif report_config != metadata_config:
            coherence_issues.append({"kind": "report_metadata_configuration_mismatch"})
        stages = report.get("stages")
        if not isinstance(stages, dict) or stages.get("verification", {}).get("status") != "passed":
            coherence_issues.append({"kind": "run_report_verification_stage"})
        verification_doc, verification_errors = _json_object(run_root / "verification.json")
        coherence_issues.extend(verification_errors)
        if verification_doc is not None and verification_doc.get("status") != "passed":
            coherence_issues.append({
                "kind": "archived_verification_status",
                "observed": verification_doc.get("status"),
            })
    trace_checks.append(_trace_check(
        "report_metadata_coherence", coherence_issues, warnings=coherence_warnings,
    ))

    produced_issues: list[dict[str, Any]] = []
    produced = report.get("produced_files") if isinstance(report, dict) else None
    if not isinstance(produced, dict):
        produced_issues.append({"kind": "produced_files_type"})
        produced = {}
    else:
        for relative, expected_hash in produced.items():
            path = run_root / relative
            if not path.is_file():
                produced_issues.append({"kind": "sealed_file_missing", "path": relative})
            elif not isinstance(expected_hash, str) or len(expected_hash) != 64:
                produced_issues.append({"kind": "sealed_hash_invalid", "path": relative})
            else:
                observed_hash = sha256(path)
                if observed_hash != expected_hash.lower():
                    produced_issues.append({
                        "kind": "sealed_file_hash",
                        "path": relative,
                        "expected": expected_hash.lower(),
                        "observed": observed_hash,
                    })
    trace_checks.append(_trace_check(
        "sealed_produced_file_hashes", produced_issues, physical_files=len(produced),
    ))

    inventory_issues: list[dict[str, Any]] = []
    observed_inventory = {
        str(path.relative_to(run_root)).replace("\\", "/")
        for path in run_root.rglob("*")
        if path.is_file()
    }
    expected_inventory = set(produced) | {"run_report.json", "COMPLETE.json"}
    missing_inventory = sorted(expected_inventory - observed_inventory)
    unexpected_inventory = sorted(observed_inventory - expected_inventory)
    if missing_inventory:
        inventory_issues.append({"kind": "sealed_inventory_missing", "files": missing_inventory})
    if unexpected_inventory:
        inventory_issues.append({"kind": "sealed_inventory_unexpected", "files": unexpected_inventory})
    trace_checks.append(_trace_check(
        "sealed_inventory", inventory_issues,
        observed_files=len(observed_inventory), expected_files=len(expected_inventory),
    ))

    configuration_issues: list[dict[str, Any]] = []
    configuration_warnings: list[dict[str, Any]] = []
    recorded_config = metadata.get("configuration_files") if isinstance(metadata, dict) else None
    if isinstance(recorded_config, dict):
        for name, expected_hash in recorded_config.items():
            archived = run_root / "inputs" / "config" / name
            current = package_root / "config" / name
            if archived.is_file():
                observed_hash = sha256(archived)
                if observed_hash != expected_hash:
                    configuration_issues.append({
                        "kind": "archived_configuration_hash", "file": name,
                        "expected": expected_hash, "observed": observed_hash,
                    })
            elif legacy and current.is_file() and sha256(current) == expected_hash:
                configuration_warnings.append({
                    "kind": "legacy_configuration_validated_against_current_package", "file": name,
                })
            elif legacy:
                configuration_warnings.append({
                    "kind": "legacy_configuration_snapshot_unavailable", "file": name,
                })
            else:
                configuration_issues.append({"kind": "archived_configuration_missing", "file": name})
        if not legacy and "tolerances.json" not in recorded_config:
            configuration_issues.append({"kind": "tolerance_hash_missing"})
    trace_checks.append(_trace_check(
        "configuration_provenance", configuration_issues, warnings=configuration_warnings,
    ))

    current_relation = "historical"
    if report is not None and metadata is not None:
        current_config = {
            name: sha256(package_root / "config" / name)
            for name in ("benchmark.json", "scenarios.json", "package.json", "tolerances.json")
        }
        if (
            report.get("source_tree_sha256") == _tree_hash(package_root)
            and metadata.get("configuration_files") == current_config
        ):
            current_relation = "current"
    trace_checks.append(_trace_check(
        "package_identity_relation",
        [],
        relation=current_relation,
        legacy_run_schema=legacy,
        note=(
            "A historical relation is not a failure: sealed internal hashes are checked, "
            "and the run is not relabelled as produced by the current source tree."
        ),
    ))

    trace_failures = [check for check in trace_checks if check["status"] != "passed"]
    overall = "passed" if results["status"] == "passed" and not trace_failures else "failed"
    archived_p3_status = "not_recorded"
    if isinstance(report, dict) and isinstance(report.get("stages"), dict):
        archived_p3 = report["stages"].get("independent_oracles")
        if isinstance(archived_p3, dict):
            archived_p3_status = archived_p3.get("status", "not_recorded")
    completed_results = dict(results)
    completed_results.pop("pending", None)
    return {
        "status": overall,
        "verification_scope": "completed_run",
        "run_identity": {
            "relation_to_current_package": current_relation,
            "legacy_run_schema": legacy,
            "package_version": report.get("package_version") if report else None,
            "source_tree_sha256": report.get("source_tree_sha256") if report else None,
        },
        "result_verification": completed_results,
        "traceability": {
            "status": "passed" if not trace_failures else "failed",
            "checks_total": len(trace_checks),
            "checks_passed": len(trace_checks) - len(trace_failures),
            "checks_failed": len(trace_failures),
            "checks": trace_checks,
        },
        "counts": {
            "result_checks": results["checks_total"],
            "result_figure_files": results["physical_output_files"],
            "traceability_checks": len(trace_checks),
            "sealed_files": len(observed_inventory),
        },
        "execution_status": {
            "result_verification": {
                "status": results["status"],
                "executed_current_invocation": True,
            },
            "completed_run_traceability": {
                "status": "passed" if not trace_failures else "failed",
                "executed_current_invocation": True,
            },
            "independent_oracles_P3": {
                "archived_status": archived_p3_status,
                "archived_source": "run_report.json:stages.independent_oracles",
                "reexecuted_current_invocation": False,
            },
        },
        "pending": {
            "editorial_figure_equivalence_P4": "not_run",
            "book_correspondence_P4": "not_run",
            "clean_environments_and_CI_P5": "not_run",
        },
    }
