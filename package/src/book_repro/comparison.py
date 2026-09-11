"""Semantic cross-environment comparison of sealed scientific runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_tolerances
from .verification import _compare_csv, normalized_text_sha256, sha256, verify_run


EXACT_AUXILIARY_FILES = (
    "independent/oracle_results.json",
    "independent/production_observations.json",
)


def _pair(package_root: Path, left: Path, right: Path, name: str) -> dict[str, Any]:
    manifest = json.loads((package_root / "reference" / "manifest.json").read_text(encoding="utf-8"))
    tolerances = load_tolerances(package_root)
    checks: list[dict[str, Any]] = []
    for item in manifest["files"]:
        if item["type"] == "pdf_basic":
            continue
        left_path = left / item["generated_path"]
        right_path = right / item["generated_path"]
        check: dict[str, Any] = {
            "id": item["id"],
            "path": item["generated_path"],
            "type": item["type"],
        }
        if item["type"] == "csv":
            check.update(_compare_csv(
                left_path,
                right_path,
                item["keys"],
                tolerances["atol"],
                tolerances["rtol"],
            ))
        elif item["type"] in {"text", "svg"}:
            left_hash = normalized_text_sha256(left_path)
            right_hash = normalized_text_sha256(right_path)
            check.update({
                "status": "passed" if left_hash == right_hash else "failed",
                "left_sha256": sha256(left_path),
                "right_sha256": sha256(right_path),
                "left_normalized_sha256": left_hash,
                "right_normalized_sha256": right_hash,
                "comparison_policy": "exact_utf8_text_after_line_ending_normalization",
                "issues": [] if left_hash == right_hash else [
                    {"kind": "hash_mismatch", "comparison": "normalized_utf8_text"}
                ],
            })
        else:
            left_hash = sha256(left_path)
            right_hash = sha256(right_path)
            check.update({
                "status": "passed" if left_hash == right_hash else "failed",
                "left_sha256": left_hash,
                "right_sha256": right_hash,
                "issues": [] if left_hash == right_hash else [{"kind": "hash_mismatch"}],
            })
        checks.append(check)
    for relative in EXACT_AUXILIARY_FILES:
        left_path = left / relative
        right_path = right / relative
        left_value = json.loads(left_path.read_text(encoding="utf-8"))
        right_value = json.loads(right_path.read_text(encoding="utf-8"))
        same = left_value == right_value
        checks.append({
            "id": f"exact_{Path(relative).stem}",
            "path": relative,
            "type": "json_exact",
            "status": "passed" if same else "failed",
            "left_sha256": sha256(left_path),
            "right_sha256": sha256(right_path),
            "issues": [] if same else [{"kind": "json_value_mismatch"}],
        })
    failures = [check for check in checks if check["status"] != "passed"]
    return {
        "name": name,
        "status": "passed" if not failures else "failed",
        "left": str(left.resolve()),
        "right": str(right.resolve()),
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failures),
        "checks_failed": len(failures),
        "numeric_tolerance": {"atol": tolerances["atol"], "rtol": tolerances["rtol"]},
        "text_policy": "UTF-8 content is exact after normalizing CRLF, CR and LF to LF; frozen reference bytes remain hash-protected.",
        "pdf_policy": "PDF binaries are excluded; their source coordinates, tables, labels and SVGs are compared.",
        "checks": checks,
    }


def compare_runs(
    package_root: Path,
    windows_run: Path,
    linux_run: Path,
    baseline_run: Path | None,
    output: Path | None = None,
) -> dict[str, Any]:
    """Compare Windows, Linux and the P4 baseline without rewriting any run."""
    package_root = package_root.resolve()
    runs: dict[str, Path] = {
        "windows": windows_run.resolve(),
        "linux": linux_run.resolve(),
    }
    if baseline_run is not None:
        runs["baseline"] = baseline_run.resolve()
    validations = {name: verify_run(package_root, path) for name, path in runs.items()}
    pairs = [_pair(package_root, runs["windows"], runs["linux"], "windows_vs_linux")]
    if "baseline" in runs:
        pairs.extend([
            _pair(package_root, runs["windows"], runs["baseline"], "windows_vs_run_015"),
            _pair(package_root, runs["linux"], runs["baseline"], "linux_vs_run_015"),
        ])
    status = "passed" if all(v["status"] == "passed" for v in validations.values()) and all(
        pair["status"] == "passed" for pair in pairs
    ) else "failed"
    report = {
        "schema_version": 1,
        "status": status,
        "runs": {name: str(path) for name, path in runs.items()},
        "run_validation": {
            name: {
                "status": value["status"],
                "relation_to_current_package": value["run_identity"]["relation_to_current_package"],
                "source_tree_sha256": value["run_identity"]["source_tree_sha256"],
            }
            for name, value in validations.items()
        },
        "pairs": pairs,
        "scope": [
            "cases A-E and classifications",
            "cash and balance-sheet ledgers",
            "accounting controls",
            "exact and floating frontiers",
            "optimization maxima",
            "sensitivities and conditional regions",
            "units, labels and generated LaTeX tables",
            "P3 independent-oracle and observation documents",
        ],
    }
    if output is not None:
        output = output.resolve()
        if output.exists():
            raise FileExistsError(f"Comparison output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
