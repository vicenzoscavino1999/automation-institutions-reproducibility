"""Preserved mutation campaign for verifier and sealed-run failure modes."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any, Callable

from .independent import run_independent_checks
from .verification import verify_run


def _load_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    return rows[0], rows[1:]


def _save_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _cell(path: Path, key_column: str, key_value: str, column: str, value: str) -> None:
    header, rows = _load_csv(path)
    key_index, value_index = header.index(key_column), header.index(column)
    target = next(row for row in rows if row[key_index] == key_value)
    target[value_index] = value
    _save_csv(path, header, rows)


def _all_issues(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks = [
        *report.get("result_verification", {}).get("checks", []),
        *report.get("traceability", {}).get("checks", []),
    ]
    return [issue for check in checks for issue in check.get("issues", [])]


def _expected_match(issue: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(issue.get(key) == value for key, value in expected.items())


def run_mutation_campaign(package_root: Path, baseline_run: Path, evidence_root: Path) -> dict[str, Any]:
    """Copy a valid run, alter one declared object, and preserve each rejection."""
    package_root = package_root.resolve()
    baseline_run = baseline_run.resolve()
    evidence_root = evidence_root.resolve()
    if evidence_root.exists():
        raise FileExistsError(f"Mutation evidence destination already exists: {evidence_root}")
    evidence_root.mkdir(parents=True)
    baseline_report = verify_run(package_root, baseline_run)
    if baseline_report["status"] != "passed":
        raise AssertionError("Mutation campaign requires a valid sealed baseline run.")

    def mutate_e(run: Path) -> None:
        _cell(run / "results" / "constructive_case.csv", "scenario", "E", "O_1", "5.25")

    def mutate_receiver(run: Path) -> None:
        _cell(run / "results" / "constructive_case_ledger_entries.csv", "entry_id", "E-D0-TRANSFER-R", "counterparty", "wrong_counterparty")

    def mutate_deposit(run: Path) -> None:
        _cell(run / "results" / "constructive_case_ledger_entries.csv", "entry_id", "E-D0-RESERVE-POSITION-L", "liability_change", "0")

    def remove_row(run: Path) -> None:
        path = run / "results" / "scenarios.csv"
        header, rows = _load_csv(path)
        _save_csv(path, header, rows[1:])

    def duplicate_row(run: Path) -> None:
        path = run / "results" / "scenarios.csv"
        header, rows = _load_csv(path)
        _save_csv(path, header, rows + [list(rows[0])])

    def extra_cell(run: Path) -> None:
        path = run / "results" / "constructive_case.csv"
        header, rows = _load_csv(path)
        rows[0].append("UNREGISTERED_EXTRA_CELL")
        _save_csv(path, header, rows)

    def short_row(run: Path) -> None:
        path = run / "results" / "constructive_case.csv"
        header, rows = _load_csv(path)
        rows[0].pop()
        _save_csv(path, header, rows)

    def mutate_unit(run: Path) -> None:
        _cell(run / "results" / "parameters.csv", "symbol", "omega_H", "unit", "wrong unit")

    def mutate_class(run: Path) -> None:
        _cell(run / "results" / "constructive_case_ledger_entries.csv", "entry_id", "E-D0-AUTOMATION-P", "economic_class", "wrong_class")

    def remove_file(run: Path) -> None:
        (run / "results" / "scenarios.csv").unlink()

    def add_file(run: Path) -> None:
        (run / "results" / "unexpected.csv").write_text("x\n1\n", encoding="utf-8")

    def mutate_text_hash(run: Path) -> None:
        path = run / "results" / "scenarios_table.tex"
        path.write_text(path.read_text(encoding="utf-8") + "% mutation\n", encoding="utf-8")

    def mutate_key(run: Path) -> None:
        _cell(run / "results" / "scenarios.csv", "scenario", "A", "scenario", "AX")

    def mutate_nan(run: Path) -> None:
        _cell(run / "results" / "constructive_case.csv", "scenario", "E", "O_1", "NaN")

    def mutate_infinity(run: Path) -> None:
        _cell(run / "results" / "constructive_case.csv", "scenario", "E", "O_1", "Infinity")

    def mutate_source_hash(run: Path) -> None:
        path = run / "results" / "run_metadata.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["source_tree_sha256"] = "0" * 64
        path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")

    def remove_configuration(run: Path) -> None:
        path = run / "results" / "run_metadata.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document.pop("configuration_files")
        path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")

    def fail_report(run: Path) -> None:
        path = run / "run_report.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["status"] = "failed"
        path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")

    def mutate_completion_hash(run: Path) -> None:
        path = run / "COMPLETE.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["run_report_sha256"] = "0" * 64
        path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")

    probes: list[tuple[str, Callable[[Path], None], dict[str, Any]]] = [
        ("E_value", mutate_e, {"kind": "numeric_value", "column": "O_1"}),
        ("receiver_counterparty", mutate_receiver, {"kind": "exact_value", "column": "counterparty"}),
        ("deposit_obligation", mutate_deposit, {"kind": "numeric_value", "column": "liability_change"}),
        ("missing_row", remove_row, {"kind": "missing_rows"}),
        ("duplicate_row", duplicate_row, {"kind": "duplicate_key"}),
        ("extra_csv_cell", extra_cell, {"kind": "csv_row_length", "direction": "extra"}),
        ("short_csv_row", short_row, {"kind": "csv_row_length", "direction": "missing"}),
        ("unit", mutate_unit, {"kind": "exact_value", "column": "unit"}),
        ("classification", mutate_class, {"kind": "exact_value", "column": "economic_class"}),
        ("missing_file", remove_file, {"kind": "missing_generated_file"}),
        ("unexpected_file", add_file, {"kind": "unexpected_generated_files"}),
        ("text_hash", mutate_text_hash, {"kind": "hash_mismatch"}),
        ("key", mutate_key, {"kind": "missing_rows"}),
        ("unexpected_nan", mutate_nan, {"kind": "nonfinite"}),
        ("unexpected_infinity", mutate_infinity, {"kind": "nonfinite"}),
        ("metadata_source_hash", mutate_source_hash, {"kind": "report_metadata_mismatch", "field": "source_tree_sha256"}),
        ("metadata_configuration_removed", remove_configuration, {"kind": "metadata_missing_field", "field": "configuration_files"}),
        ("report_status", fail_report, {"kind": "run_report_status"}),
        ("completion_hash", mutate_completion_hash, {"kind": "completion_report_hash"}),
    ]
    outcomes: list[dict[str, Any]] = []
    for name, mutator, expected in probes:
        probe_root = evidence_root / name
        run = probe_root / "run"
        shutil.copytree(baseline_run, run)
        mutator(run)
        report = verify_run(package_root, run)
        issues = _all_issues(report)
        matched = any(_expected_match(issue, expected) for issue in issues)
        outcome = {
            "name": name,
            "status": "passed" if report["status"] == "failed" and matched else "failed",
            "verifier_status": report["status"],
            "expected_issue": expected,
            "expected_issue_observed": matched,
            "issues_observed": issues,
            "mutated_run": str(run),
        }
        (probe_root / "verifier_output.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        (probe_root / "outcome.json").write_text(
            json.dumps(outcome, indent=2, sort_keys=True), encoding="utf-8"
        )
        outcomes.append(outcome)
    failures = [outcome for outcome in outcomes if outcome["status"] != "passed"]
    summary = {
        "schema_version": 1,
        "status": "passed" if not failures else "failed",
        "baseline_run": str(baseline_run),
        "baseline_status": baseline_report["status"],
        "probes_total": len(outcomes),
        "probes_passed": len(outcomes) - len(failures),
        "probes_failed": len(failures),
        "outcomes": outcomes,
    }
    (evidence_root / "campaign_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    return summary


def run_p3_coverage_campaign(
    package_root: Path,
    baseline_run: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    """Prove that P3 itself rejects mutations not delegated to references."""
    package_root = package_root.resolve()
    baseline_run = baseline_run.resolve()
    evidence_root = evidence_root.resolve()
    if evidence_root.exists():
        raise FileExistsError(f"P3 evidence destination already exists: {evidence_root}")
    evidence_root.mkdir(parents=True)
    baseline = run_independent_checks(package_root, baseline_run)
    if baseline["status"] != "passed":
        raise AssertionError("P3 coverage campaign requires a valid P3 baseline.")

    def mutate_json(run: Path, route: tuple[Any, ...], value: Any) -> None:
        path = run / "independent" / "production_observations.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        target: Any = document
        for part in route[:-1]:
            target = target[part]
        target[route[-1]] = value
        path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")

    def independent_issues(report: dict[str, Any], group: str) -> list[dict[str, Any]]:
        check = next((item for item in report["checks"] if item["id"] == group), None)
        if not check:
            return []
        evidence = check.get("evidence")
        return evidence.get("issues", []) if isinstance(evidence, dict) else []

    probes: list[tuple[str, Callable[[Path], None], str, dict[str, Any]]] = [
        (
            "demand_frontier",
            lambda run: _cell(run / "results" / "fixed_policy_gate_thresholds.csv", "opportunity_status", "interior_threshold", "demand_m_h_max", "0.75"),
            "A05_exact_frontiers_and_inclusive_boundaries",
            {"kind": "observed_numeric_mismatch", "field": "demand_m_h_max"},
        ),
        (
            "capacity_frontier",
            lambda run: _cell(run / "results" / "fixed_policy_gate_thresholds.csv", "opportunity_status", "interior_threshold", "opportunity_phi_min", "0.9"),
            "A05_exact_frontiers_and_inclusive_boundaries",
            {"kind": "observed_numeric_mismatch", "field": "opportunity_phi_min"},
        ),
        (
            "investment_minimum",
            lambda run: _cell(run / "results" / "analytical_conditions.csv", "capacity_case", "high", "I_min", "99"),
            "A07_minima_already_satisfied_and_ceiling",
            {"kind": "observed_numeric_mismatch", "field": "I_min"},
        ),
        (
            "optimal_value",
            lambda run: _cell(run / "results" / "optimization_summary.csv", "case", "productive_investment_ceiling", "delta_demand_max", "99"),
            "A10_vertex_enumeration_with_and_without_cap",
            {"kind": "observed_numeric_mismatch", "field": "delta_demand_max"},
        ),
        (
            "optimal_allocation",
            lambda run: _cell(run / "results" / "optimization_summary.csv", "case", "productive_investment_ceiling", "investment", "99"),
            "A10_vertex_enumeration_with_and_without_cap",
            {"kind": "observed_numeric_mismatch", "field": "investment"},
        ),
        (
            "missing_frontier_file",
            lambda run: (run / "results" / "fixed_policy_gate_thresholds.csv").unlink(),
            "A05_exact_frontiers_and_inclusive_boundaries",
            {"kind": "missing_observed_file"},
        ),
        (
            "missing_minima_file",
            lambda run: (run / "results" / "analytical_conditions.csv").unlink(),
            "A07_minima_already_satisfied_and_ceiling",
            {"kind": "missing_observed_file"},
        ),
        (
            "missing_optimization_file",
            lambda run: (run / "results" / "optimization_summary.csv").unlink(),
            "A10_vertex_enumeration_with_and_without_cap",
            {"kind": "missing_observed_file"},
        ),
        (
            "missing_edge_observations",
            lambda run: (run / "independent" / "production_observations.json").unlink(),
            "A06_capacity_projection_corners",
            {"kind": "missing_observed_file"},
        ),
        (
            "projection_observation",
            lambda run: mutate_json(run, ("projection", 3, "projected"), 0.9),
            "A06_capacity_projection_corners",
            {"kind": "observed_numeric_mismatch", "field": "projected"},
        ),
        (
            "already_satisfied_observation",
            lambda run: mutate_json(run, ("opportunity_requirements", "already_satisfied", "status"), "wrong"),
            "A07_minima_already_satisfied_and_ceiling",
            {"kind": "observed_exact_mismatch", "field": "status"},
        ),
        (
            "technical_limit_observation",
            lambda run: mutate_json(run, ("opportunity_requirements", "technically_impossible", "investment_min"), 0.0),
            "A07_minima_already_satisfied_and_ceiling",
            {"kind": "observed_null_mismatch", "field": "investment_min"},
        ),
        (
            "operation_insufficient_observation",
            lambda run: mutate_json(run, ("operation_insufficient", "threshold", "opportunity_status"), "interior_threshold"),
            "A08_operation_insufficient_at_capacity_ceiling",
            {"kind": "observed_exact_mismatch", "field": "opportunity_status"},
        ),
        (
            "finance_shortfall_observation",
            lambda run: mutate_json(run, ("fiscal_edge_cases", "finance_shortfall", "resources"), 7.0),
            "A09_zero_capture_and_finance_shortfall",
            {"kind": "observed_numeric_mismatch", "field": "resources"},
        ),
        (
            "zero_capture_observation",
            lambda run: mutate_json(run, ("fiscal_edge_cases", "zero_capture", "tax"), 1.0),
            "A09_zero_capture_and_finance_shortfall",
            {"kind": "observed_numeric_mismatch", "field": "tax"},
        ),
        (
            "constant_objective_observation",
            lambda run: mutate_json(run, ("constant_objective", "observations", 1, "direct_demand"), 1.0),
            "A11_constant_objective_equal_coefficients",
            {"kind": "observed_numeric_mismatch", "field": "direct_demand"},
        ),
    ]

    outcomes: list[dict[str, Any]] = []
    for name, mutator, expected_group, expected_issue in probes:
        probe_root = evidence_root / name
        run = probe_root / "run"
        shutil.copytree(baseline_run, run)
        mutator(run)
        report = run_independent_checks(package_root, run)
        issues = independent_issues(report, expected_group)
        group = next(item for item in report["checks"] if item["id"] == expected_group)
        matched = any(_expected_match(issue, expected_issue) for issue in issues)
        outcome = {
            "name": name,
            "status": "passed" if report["status"] == "failed" and group["status"] == "failed" and matched else "failed",
            "p3_status": report["status"],
            "expected_group": expected_group,
            "observed_group_status": group["status"],
            "expected_issue": expected_issue,
            "expected_issue_observed": matched,
            "reference_verifier_called": False,
            "mutated_run": str(run),
        }
        (probe_root / "p3_output.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
        (probe_root / "outcome.json").write_text(
            json.dumps(outcome, indent=2, sort_keys=True), encoding="utf-8"
        )
        outcomes.append(outcome)
    failures = [outcome for outcome in outcomes if outcome["status"] != "passed"]
    summary = {
        "schema_version": 1,
        "stage": "P3_independent_comparison_only",
        "status": "passed" if not failures else "failed",
        "baseline_run": str(baseline_run),
        "baseline_p3_status": baseline["status"],
        "reference_verifier_called": False,
        "probes_total": len(outcomes),
        "probes_passed": len(outcomes) - len(failures),
        "probes_failed": len(failures),
        "outcomes": outcomes,
    }
    (evidence_root / "campaign_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    return summary
