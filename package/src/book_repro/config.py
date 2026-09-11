"""Load the single declared parameter and policy configuration."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

from .model import FiscalInstrument, Parameters, Policy


def package_root() -> Path:
    declared = os.environ.get("BOOK_REPRO_ROOT")
    if declared:
        root = Path(declared).resolve()
        if not (root / "config" / "package.json").is_file():
            raise FileNotFoundError(f"BOOK_REPRO_ROOT is not a package root: {root}")
        return root
    return Path(__file__).resolve().parents[2]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().lower()


def load_tolerances(root: Path | None = None) -> dict:
    """Load and strictly validate the numeric-comparison contract.

    Python's JSON decoder accepts non-standard ``NaN``/``Infinity`` tokens by
    default, and booleans are subclasses of integers.  Both behaviours are
    rejected here so a malformed tolerance can never disable a comparison.
    """
    root = (root or package_root()).resolve()
    path = root / "config" / "tolerances.json"
    document = read_json(path)
    if not isinstance(document, dict):
        raise ValueError("tolerances.json must contain a JSON object.")
    required_top = {"schema_version", "floating_point", "exact_fields"}
    missing_top = sorted(required_top - set(document))
    if missing_top:
        raise ValueError(f"tolerances.json is missing fields: {missing_top}.")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("tolerances.json schema_version must be integer 1.")
    if not isinstance(document["exact_fields"], str) or not document["exact_fields"].strip():
        raise ValueError("tolerances.json exact_fields must be a non-empty string.")
    floating = document["floating_point"]
    if not isinstance(floating, dict):
        raise ValueError("tolerances.json floating_point must be an object.")
    required_floating = {"atol", "rtol", "reason"}
    missing_floating = sorted(required_floating - set(floating))
    if missing_floating:
        raise ValueError(
            f"tolerances.json floating_point is missing fields: {missing_floating}."
        )
    if not isinstance(floating["reason"], str) or not floating["reason"].strip():
        raise ValueError("floating_point.reason must be a non-empty string.")
    validated: dict[str, float] = {}
    for field in ("atol", "rtol"):
        value = floating[field]
        if type(value) not in {int, float}:
            raise ValueError(f"floating_point.{field} must be a JSON number.")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"floating_point.{field} must be finite.")
        if number < 0:
            raise ValueError(f"floating_point.{field} must be nonnegative.")
        validated[field] = number
    return {
        "schema_version": 1,
        "atol": validated["atol"],
        "rtol": validated["rtol"],
        "reason": floating["reason"],
        "exact_fields": document["exact_fields"],
        "sha256": sha256(path),
    }


def load_configuration(root: Path | None = None) -> tuple[Parameters, list[Policy], dict]:
    root = (root or package_root()).resolve()
    benchmark_path = root / "config" / "benchmark.json"
    scenarios_path = root / "config" / "scenarios.json"
    package_path = root / "config" / "package.json"
    tolerances_path = root / "config" / "tolerances.json"
    benchmark = read_json(benchmark_path)
    scenarios_document = read_json(scenarios_path)
    package = read_json(package_path)
    tolerances = load_tolerances(root)
    parameters = Parameters(**benchmark["parameters"])
    parameters.validate()
    policies: list[Policy] = []
    for item in scenarios_document["scenarios"]:
        fiscal = FiscalInstrument(**item["fiscal"])
        policy_fields = {key: value for key, value in item.items() if key != "fiscal"}
        policy = Policy(fiscal=fiscal, **policy_fields)
        policy.validate(parameters)
        policies.append(policy)
    names = [policy.name for policy in policies]
    if names != ["A", "B", "C", "D"]:
        raise ValueError(f"Scenario order and identity must be A-D; observed {names}.")
    settings = {
        **benchmark["generation"],
        "package": package,
        "tolerances": tolerances,
        "configuration_files": {
            "benchmark.json": sha256(benchmark_path),
            "scenarios.json": sha256(scenarios_path),
            "package.json": sha256(package_path),
            "tolerances.json": sha256(tolerances_path),
        },
    }
    return parameters, policies, settings
