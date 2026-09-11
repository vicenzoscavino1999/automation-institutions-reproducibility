"""Validate and summarize the static whole-book coverage registry.

The default check is deliberately structural so that a reader can validate the
distributed package without receiving the book manuscript. Passing an
identified manuscript adds a source-backed validation of labels and locators.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_CLASSES = {
    "analytical_support_located",
    "support_pending",
    "finite_computational_check",
    "reproduced_numeric_result",
    "conceptual_explanation",
    "unimplemented_module",
}

SUPPORT_KINDS = {
    "own_proof",
    "argument_in_statement",
    "adjacent_derivation",
    "support_pending",
}

PROOF_FORMS = {"proof_environment", "named_proof_section"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_span(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("start_line"), int)
        and isinstance(value.get("end_line"), int)
        and 0 < value["start_line"] <= value["end_line"]
    )


def _line_text(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start - 1 : end])


def validate_registry_data(
    registry: dict[str, Any], manuscript: Path | None = None
) -> list[dict[str, Any]]:
    """Return structural and, optionally, manuscript-backed registry issues."""

    issues: list[dict[str, Any]] = []
    units = registry.get("units", [])
    results = registry.get("formal_results", [])
    unit_ids = [unit.get("id") for unit in units]
    result_ids = [item.get("id") for item in results]
    labels = [item.get("latex_label") for item in results]

    if registry.get("schema_version") != 2:
        issues.append({"kind": "unsupported_registry_schema", "observed": registry.get("schema_version")})
    if len(unit_ids) != len(set(unit_ids)):
        issues.append({"kind": "duplicate_unit_id"})
    if len(result_ids) != len(set(result_ids)):
        issues.append({"kind": "duplicate_result_id"})
    if len(labels) != len(set(labels)):
        issues.append({"kind": "duplicate_latex_label"})

    chapters = sorted(unit.get("number") for unit in units if unit.get("kind") == "chapter")
    if chapters != list(range(1, 17)):
        issues.append({"kind": "chapter_coverage", "observed": chapters})
    appendices = [unit for unit in units if unit.get("kind") in {"appendix", "reference_tables"}]
    if len(appendices) != 15:
        issues.append({"kind": "appendix_coverage", "observed": len(appendices), "expected": 15})

    for unit in units:
        classes = unit.get("coverage_classes", [])
        unknown = sorted(set(classes) - ALLOWED_CLASSES)
        if unknown:
            issues.append({"kind": "unknown_coverage_class", "unit": unit.get("id"), "values": unknown})

    for result in results:
        result_id = result.get("id")
        if result.get("unit_id") not in unit_ids:
            issues.append({"kind": "unknown_result_unit", "result": result_id})
        if result.get("support_class") not in ALLOWED_CLASSES:
            issues.append({"kind": "unknown_result_class", "result": result_id})
        statement = result.get("statement_locator")
        if not result.get("latex_label") or not _valid_span(statement):
            issues.append({"kind": "incomplete_result_locator", "result": result_id})
        hypotheses = result.get("hypotheses")
        if not isinstance(hypotheses, dict) or hypotheses.get("status") != "located_in_formal_statement" or not _valid_span(hypotheses):
            issues.append({"kind": "incomplete_hypothesis_locator", "result": result_id})

        support = result.get("analytical_support", {})
        support_status = support.get("status")
        support_kind = support.get("kind")
        if support_status not in {"located", "pending"} or support_kind not in SUPPORT_KINDS:
            issues.append({"kind": "invalid_support_classification", "result": result_id})
        elif support_status == "pending":
            if support_kind != "support_pending" or support.get("start_line") is not None or support.get("end_line") is not None:
                issues.append({"kind": "invalid_pending_support", "result": result_id})
        else:
            if support_kind == "support_pending" or not _valid_span(support):
                issues.append({"kind": "incomplete_support_locator", "result": result_id})
            if support.get("associated_label") != result.get("latex_label"):
                issues.append({"kind": "support_label_mismatch", "result": result_id})
            if support_kind == "own_proof" and support.get("form") not in PROOF_FORMS:
                issues.append({"kind": "invalid_proof_form", "result": result_id})

    if manuscript is None:
        return issues

    manuscript = manuscript.resolve()
    if not manuscript.is_file():
        issues.append({"kind": "manuscript_missing", "path": str(manuscript)})
        return issues
    observed_hash = _sha256(manuscript)
    if observed_hash != registry.get("manuscript_sha256"):
        issues.append({
            "kind": "manuscript_hash_mismatch",
            "expected": registry.get("manuscript_sha256"),
            "observed": observed_hash,
        })
        return issues

    lines = manuscript.read_text(encoding="utf-8").splitlines()
    total_lines = len(lines)
    ordered = sorted(
        (item for item in results if _valid_span(item.get("statement_locator"))),
        key=lambda item: item["statement_locator"]["start_line"],
    )
    statement_spans = [
        (item["statement_locator"]["start_line"], item["statement_locator"]["end_line"], item.get("latex_label"))
        for item in ordered
    ]

    for index, result in enumerate(ordered):
        result_id = result.get("id")
        label = result.get("latex_label")
        environment = result.get("environment")
        statement = result["statement_locator"]
        if statement["end_line"] > total_lines:
            issues.append({"kind": "invalid_statement_line", "result": result_id, "line": statement["end_line"]})
            continue
        statement_text = _line_text(lines, statement["start_line"], statement["end_line"])
        if not re.search(rf"\\begin\{{{re.escape(str(environment))}\}}", statement_text):
            issues.append({"kind": "statement_environment_mismatch", "result": result_id})
        if rf"\label{{{label}}}" not in statement_text:
            issues.append({"kind": "statement_label_mismatch", "result": result_id})
        if not re.search(rf"\\end\{{{re.escape(str(environment))}\}}", statement_text):
            issues.append({"kind": "statement_end_mismatch", "result": result_id})

        hypotheses = result.get("hypotheses", {})
        if _valid_span(hypotheses) and not (
            statement["start_line"] <= hypotheses["start_line"] <= hypotheses["end_line"] <= statement["end_line"]
        ):
            issues.append({"kind": "hypotheses_outside_statement", "result": result_id})
        for dependency in result.get("dependencies", []):
            dependency_label = dependency.get("latex_label")
            if not dependency_label or not re.search(rf"\\(?:eq)?ref\{{{re.escape(str(dependency_label))}\}}", statement_text):
                issues.append({"kind": "dependency_not_in_statement", "result": result_id, "label": dependency_label})

        support = result.get("analytical_support", {})
        if support.get("status") != "located" or not _valid_span(support):
            continue
        start = support["start_line"]
        end = support["end_line"]
        if end > total_lines:
            issues.append({"kind": "invalid_support_line", "result": result_id, "line": end})
            continue
        support_text = _line_text(lines, start, end)
        kind = support.get("kind")
        if kind == "argument_in_statement" and not (
            statement["start_line"] <= start <= end <= statement["end_line"]
        ):
            issues.append({"kind": "argument_outside_statement", "result": result_id})
        elif kind == "own_proof":
            proof_form = support.get("form")
            if proof_form == "named_proof_section":
                # Associate a named proof through its opening heading. A
                # reference in the body of another result's proof is use of
                # the target result, not evidence that the proof belongs to it.
                first_line = support_text.splitlines()[0] if support_text else ""
                has_heading = re.fullmatch(
                    r"\\(?:chapter|section|subsection)\*?\{[^\n]*(?:Proof|proof|Derivation|derivation)[^\n]*\}",
                    first_line.strip(),
                )
                has_own_reference = bool(has_heading) and rf"\ref{{{label}}}" in first_line
                if not has_heading or not has_own_reference:
                    issues.append({"kind": "named_proof_label_mismatch", "result": result_id})
            elif proof_form == "proof_environment":
                next_statement_line = (
                    ordered[index + 1]["statement_locator"]["start_line"]
                    if index + 1 < len(ordered) else total_lines + 1
                )
                if r"\begin{proof}" not in support_text or r"\end{proof}" not in support_text:
                    issues.append({"kind": "proof_environment_missing", "result": result_id})
                if start < statement["end_line"] or end >= next_statement_line:
                    issues.append({"kind": "proof_associated_with_other_result", "result": result_id})
        if kind in {"own_proof", "adjacent_derivation"}:
            for other_start, other_end, other_label in statement_spans:
                if other_label != label and not (end < other_start or start > other_end):
                    issues.append({
                        "kind": "support_overlaps_other_result",
                        "result": result_id,
                        "other_label": other_label,
                    })
                    break

    return issues


def coverage_report(
    package_root: Path,
    output: Path | None = None,
    manuscript: Path | None = None,
) -> dict[str, Any]:
    path = package_root.resolve() / "config" / "coverage.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    issues = validate_registry_data(registry, manuscript)
    units = registry.get("units", [])
    results = registry.get("formal_results", [])
    chapters = sorted(unit.get("number") for unit in units if unit.get("kind") == "chapter")
    appendices = [unit for unit in units if unit.get("kind") in {"appendix", "reference_tables"}]
    counts = Counter(
        coverage_class
        for unit in units
        for coverage_class in unit.get("coverage_classes", [])
    )
    support_status_counts = Counter(
        item.get("analytical_support", {}).get("status") for item in results
    )
    support_kind_counts = Counter(
        item.get("analytical_support", {}).get("kind") for item in results
    )
    validation_mode = "manuscript_backed" if manuscript is not None else "structural_only"
    report = {
        "schema_version": 2,
        "status": "passed" if not issues else "failed",
        "validation_mode": validation_mode,
        "registry": str(path),
        "manuscript_path": str(manuscript.resolve()) if manuscript is not None else None,
        "manuscript_validation": "passed" if manuscript is not None and not issues else ("failed" if manuscript is not None else "not_run"),
        "manuscript_version": registry.get("manuscript_version"),
        "manuscript_sha256": registry.get("manuscript_sha256"),
        "units_total": len(units),
        "chapters_total": len(chapters),
        "appendix_and_reference_units_total": len(appendices),
        "formal_results_total": len(results),
        "coverage_class_occurrences": dict(sorted(counts.items())),
        "support_status_counts": dict(sorted(support_status_counts.items())),
        "support_kind_counts": dict(sorted(support_kind_counts.items())),
        "issues": issues,
        "scope_note": registry.get("scope_note"),
    }
    if output is not None:
        output = output.resolve()
        if output.exists():
            raise FileExistsError(f"Coverage output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
