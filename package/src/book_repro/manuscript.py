"""Read-only P4 correspondence checks against an identified manuscript copy."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from .editorial import sha256
from .verification import verify_run


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Claim source is missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _one(rows: list[dict[str, str]], key: dict[str, str]) -> dict[str, str]:
    matches = [row for row in rows if all(row.get(name) == value for name, value in key.items())]
    if len(matches) != 1:
        raise ValueError(f"Expected one source row for {key}; observed {len(matches)}.")
    return matches[0]


def _resolve_sources(run: Path, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved = []
    for source in sources:
        path = run / source["file"]
        row = _one(_read_csv(path), source["key"])
        values = {}
        for field in source["fields"]:
            if field not in row:
                raise KeyError(f"Field {field!r} is absent from {source['file']}.")
            values[field] = row[field]
        resolved.append({"file": source["file"], "key": source["key"], "fields": values})
    return resolved


def _label_context(text: str, label: str, radius: int = 1800) -> tuple[str, list[dict[str, Any]]]:
    token = rf"\label{{{label}}}"
    positions = [match.start() for match in re.finditer(re.escape(token), text)]
    if len(positions) != 1:
        return "", [{"kind": "label_count", "label": label, "expected": 1, "observed": len(positions)}]
    index = positions[0]
    return text[max(0, index - radius): min(len(text), index + radius)], []


def _environment(text: str, label: str, environment: str) -> tuple[str, list[dict[str, Any]]]:
    context, issues = _label_context(text, label, radius=6000)
    if issues:
        return "", issues
    label_token = rf"\label{{{label}}}"
    index = context.index(label_token)
    begin_pattern = re.compile(rf"\\begin\{{{re.escape(environment)}\}}(?:\[[^\]]*\])?")
    starts = [match.start() for match in begin_pattern.finditer(context[:index])]
    end_token = rf"\end{{{environment}}}"
    end = context.find(end_token, index)
    if not starts or end < 0:
        return "", [{"kind": "environment_not_found", "label": label, "environment": environment}]
    return context[starts[-1]: end + len(end_token)], []


def _formula_check(text: str, claim: dict[str, Any]) -> list[dict[str, Any]]:
    context, issues = _label_context(text, claim["latex_label"])
    if issues:
        return issues
    for token in claim["required_tex"]:
        if token not in context:
            issues.append({"kind": "required_tex_missing", "token": token})
    return issues


def _clean_cell(value: str) -> str:
    value = value.strip()
    value = value.replace(r"\phantom{-}", "")
    value = value.replace("$", "")
    return re.sub(r"\s+", " ", value).strip()


def _scenario_table_check(text: str, run: Path, claim: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    block, issues = _environment(text, claim["latex_label"], "table")
    if issues:
        return issues, []
    parameters = _read_csv(run / "results" / "parameters.csv")
    scenarios = _read_csv(run / "results" / "scenarios.csv")
    constructive = _read_csv(run / "results" / "constructive_case.csv")
    m_h = float(_one(parameters, {"symbol": "m_H=m_T"})["value"])
    rows = scenarios + constructive
    observed: dict[str, list[str]] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if re.match(r"^[A-E]\s*&", stripped):
            cells = [_clean_cell(cell) for cell in stripped.removesuffix(r"\\").split("&")]
            observed[cells[0]] = cells
    if set(observed) != set("ABCDE"):
        issues.append({"kind": "scenario_rows", "expected": list("ABCDE"), "observed": sorted(observed)})
        return issues, []
    checked = []
    for row in rows:
        name = row["scenario"]
        row_m_h = float(row["m_H"]) if name == "E" else m_h
        expected = [
            name,
            f"{row_m_h:.2f}",
            f"{float(row['phi']):.2f}",
            f"{float(row['T']):g}",
            f"{float(row['y_T']):g}",
            f"{float(row['I_q']):g}",
            f"{float(row['B_0']):g}",
            f"{float(row['delta_D0_dir']):.1f}",
            f"{float(row['O_1']):.2f}",
            "pass" if row["demand_gate"] == "True" else "fail",
            "pass" if row["opportunity_gate"] == "True" else "fail",
        ]
        actual = observed[name]
        if actual != expected:
            issues.append({"kind": "scenario_presentation", "scenario": name, "expected": expected, "observed": actual})
        checked.append({"scenario": name, "expected": expected, "observed": actual, "status": "passed" if actual == expected else "failed"})
    return issues, checked


def _fraction_tokens(value: str) -> list[str]:
    numerator, denominator = value.split("/", maxsplit=1)
    return [rf"\frac{{{numerator}}}{{{denominator}}}", rf"\frac{numerator}{denominator}"]


def _frontier_check(text: str, run: Path, claim: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    context, issues = _label_context(text, claim["latex_label"])
    if issues:
        return issues, {}
    source = _one(_read_csv(run / claim["source"]["file"]), claim["source"]["key"])
    observed_decimal = float(source[claim["source"]["field"]])
    oracle = json.loads((run / "independent" / "oracle_results.json").read_text(encoding="utf-8"))
    group = next(item for item in oracle["checks"] if item["id"] == "A05_exact_frontiers_and_inclusive_boundaries")
    exact = group["evidence"][claim["oracle_field"]]
    numerator, denominator = exact.split("/", maxsplit=1)
    expected_decimal = int(numerator) / int(denominator)
    if abs(observed_decimal - expected_decimal) > 1.0e-12:
        issues.append({"kind": "frontier_source_disagreement", "csv": observed_decimal, "exact": exact})
    if not any(token in context for token in _fraction_tokens(exact)):
        issues.append({"kind": "frontier_fraction_missing", "exact": exact})
    return issues, {"csv_value": observed_decimal, "exact": exact, "precision": claim["printed_precision"]}


def _figure_check(text: str, claim: dict[str, Any]) -> list[dict[str, Any]]:
    block, issues = _environment(text, claim["latex_label"], "figure")
    if issues:
        return issues
    if claim["graphic_path"] not in block:
        issues.append({"kind": "graphic_path_missing", "expected": claim["graphic_path"]})
    for term in claim["caption_terms"]:
        if term not in block:
            issues.append({"kind": "caption_term_missing", "term": term})
    return issues


def _anchor_check(text: str, run: Path, claim: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    issues = []
    positions = [match.start() for match in re.finditer(re.escape(claim["anchor_text"]), text)]
    if len(positions) != 1:
        return [{"kind": "anchor_count", "expected": 1, "observed": len(positions)}], {}
    context = text[positions[0]: positions[0] + claim.get("context_after", 700)]
    row = _one(_read_csv(run / claim["source"]["file"]), claim["source"]["key"])
    value = float(row[claim["source"]["field"]])
    digits = claim["printed_precision"]["digits"]
    formatted = f"{value:.{digits}f}" if digits > 0 else f"{value:.0f}"
    if formatted not in context:
        issues.append({"kind": "printed_value_missing", "expected": formatted})
    return issues, {"unrounded": row[claim["source"]["field"]], "formatted": formatted, "digits": digits}


def check_book(package_root: Path, manuscript: Path, run: Path,
               output: Path | None = None, claims_path: Path | None = None,
               require_completed_run: bool = True) -> dict[str, Any]:
    """Verify registered claims in a manuscript without modifying it or the run."""
    package_root, manuscript, run = package_root.resolve(), manuscript.resolve(), run.resolve()
    if not manuscript.is_file():
        raise FileNotFoundError(f"Manuscript was not supplied: {manuscript}")
    run_verification: dict[str, Any] | None = None
    if require_completed_run:
        run_verification = verify_run(package_root, run)
        if run_verification["status"] != "passed":
            raise AssertionError("The claim source run did not pass completed-run verification.")
        if run_verification["run_identity"]["relation_to_current_package"] != "current":
            raise AssertionError("check-book requires a run produced by the current package source tree.")
    claims_path = (claims_path or package_root / "config" / "book_claims.json").resolve()
    registry = json.loads(claims_path.read_text(encoding="utf-8"))
    before = sha256(manuscript)
    identity_issues = []
    if before != registry["manuscript_sha256"]:
        identity_issues.append({"kind": "manuscript_sha256", "expected": registry["manuscript_sha256"], "observed": before})
    text = manuscript.read_text(encoding="utf-8")
    results = []
    for claim in registry["claims"]:
        issues: list[dict[str, Any]] = []
        resolved = _resolve_sources(run, claim.get("sources", []))
        detail: Any = None
        if claim["kind"] == "formula":
            issues.extend(_formula_check(text, claim))
        elif claim["kind"] == "scenario_table":
            table_issues, detail = _scenario_table_check(text, run, claim)
            issues.extend(table_issues)
        elif claim["kind"] == "frontier":
            frontier_issues, detail = _frontier_check(text, run, claim)
            issues.extend(frontier_issues)
        elif claim["kind"] == "figure":
            issues.extend(_figure_check(text, claim))
        elif claim["kind"] == "numeric_anchor":
            anchor_issues, detail = _anchor_check(text, run, claim)
            issues.extend(anchor_issues)
        else:
            issues.append({"kind": "unsupported_claim_kind", "observed": claim["kind"]})
        results.append({
            "id": claim["id"],
            "latex_label": claim.get("latex_label"),
            "kind": claim["kind"],
            "magnitude": claim["magnitude"],
            "unit": claim["unit"],
            "scenario": claim["scenario"],
            "printed_precision": claim["printed_precision"],
            "resolved_sources": resolved,
            "detail": detail,
            "status": "passed" if not issues else "failed",
            "issues": issues,
        })
    after = sha256(manuscript)
    if after != before:
        identity_issues.append({"kind": "manuscript_modified_during_check", "before": before, "after": after})
    failures = [result for result in results if result["status"] != "passed"]
    report = {
        "schema_version": 1,
        "status": "passed" if not identity_issues and not failures else "failed",
        "manuscript": {
            "path": str(manuscript),
            "version": registry["manuscript_version"],
            "sha256_before": before,
            "sha256_after": after,
            "read_only": before == after,
            "identity_issues": identity_issues,
        },
        "run": str(run),
        "run_verification": (
            {
                "status": run_verification["status"],
                "relation_to_current_package": run_verification["run_identity"]["relation_to_current_package"],
            }
            if run_verification is not None else {"status": "not_required_test_fixture"}
        ),
        "registry": {"path": str(claims_path), "sha256": sha256(claims_path)},
        "claims_total": len(results),
        "claims_passed": len(results) - len(failures),
        "claims_failed": len(failures),
        "claims": results,
    }
    if output is not None:
        output = output.resolve()
        if output.exists():
            raise FileExistsError(f"check-book output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
