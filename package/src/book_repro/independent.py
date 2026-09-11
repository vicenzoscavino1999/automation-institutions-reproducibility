"""Independent exact-arithmetic checks for delivery 2 / P3.

The routines in this module read declared inputs and written outputs.  They do
not import or call ``book_repro.model`` or its production formulas.
"""

from __future__ import annotations

import csv
import json
from decimal import Decimal
from fractions import Fraction
from itertools import combinations, product
from pathlib import Path
from typing import Any, Iterable


F = Fraction
UNIT = "date-0 goods at P0=P1=1"


def _read_decimal_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)


def _f(value: Any) -> F:
    if isinstance(value, F):
        return value
    if isinstance(value, Decimal):
        return F(value)
    if isinstance(value, bool):
        raise TypeError("Boolean is not a numeric input.")
    return F(str(value))


def _clip_unit(value: F) -> F:
    return max(F(0), min(F(1), value))


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _safe_rows(path: Path) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    if not path.is_file():
        return [], [{"kind": "missing_observed_file", "file": path.name}]
    try:
        rows = _read_rows(path)
    except Exception as error:
        return [], [{
            "kind": "unreadable_observed_file",
            "file": path.name,
            "error": type(error).__name__,
        }]
    return rows, []


def _safe_observations(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.is_file():
        return {}, [{"kind": "missing_observed_file", "file": path.name}]
    try:
        document = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except Exception as error:
        return {}, [{
            "kind": "unreadable_observed_file",
            "file": path.name,
            "error": type(error).__name__,
        }]
    if not isinstance(document, dict):
        return {}, [{"kind": "observed_document_type", "file": path.name}]
    return document, []


def _observed_close(value: Any, expected: F, atol: float, rtol: float) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return _close(value, expected, atol, rtol)
    except (ValueError, TypeError, ZeroDivisionError):
        return False


def _compare_rows(
    filename: str,
    observed_rows: list[dict[str, str]],
    expected_rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
    numeric_fields: tuple[str, ...],
    exact_fields: tuple[str, ...],
    atol: float,
    rtol: float,
) -> list[dict[str, Any]]:
    """Compare derived expectations with written product rows by declared key."""
    issues: list[dict[str, Any]] = []

    def key(row: dict[str, Any]) -> tuple[str, ...]:
        normalized: list[str] = []
        for field in key_fields:
            value = row.get(field, "")
            if field in numeric_fields:
                try:
                    normalized.append(str(_f(value)))
                    continue
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            normalized.append(str(value))
        return tuple(normalized)

    observed_map: dict[tuple[str, ...], dict[str, str]] = {}
    for row in observed_rows:
        row_key = key(row)
        if row_key in observed_map:
            issues.append({"kind": "duplicate_observed_key", "file": filename, "key": row_key})
        observed_map[row_key] = row
    expected_map = {key(row): row for row in expected_rows}
    for row_key in sorted(expected_map.keys() - observed_map.keys()):
        issues.append({"kind": "missing_observed_row", "file": filename, "key": row_key})
    for row_key in sorted(observed_map.keys() - expected_map.keys()):
        issues.append({"kind": "unexpected_observed_row", "file": filename, "key": row_key})
    for row_key in sorted(expected_map.keys() & observed_map.keys()):
        expected, observed = expected_map[row_key], observed_map[row_key]
        for field in exact_fields:
            expected_value = expected[field]
            expected_text = str(expected_value)
            if isinstance(expected_value, bool):
                expected_text = "True" if expected_value else "False"
            if observed.get(field) != expected_text:
                issues.append({
                    "kind": "observed_exact_mismatch", "file": filename,
                    "key": row_key, "field": field,
                    "expected": expected_text, "observed": observed.get(field),
                })
        for field in numeric_fields:
            expected_value = _f(expected[field])
            if not _observed_close(observed.get(field), expected_value, atol, rtol):
                issues.append({
                    "kind": "observed_numeric_mismatch", "file": filename,
                    "key": row_key, "field": field,
                    "expected": str(expected_value), "observed": observed.get(field),
                })
    return issues


def _compare_mapping(
    location: str,
    observed: Any,
    expected: dict[str, Any],
    numeric_fields: tuple[str, ...],
    exact_fields: tuple[str, ...],
    atol: float,
    rtol: float,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(observed, dict):
        return [{"kind": "missing_observed_case", "location": location}]
    for field in exact_fields:
        if observed.get(field) != expected[field]:
            issues.append({
                "kind": "observed_exact_mismatch", "location": location,
                "field": field, "expected": expected[field], "observed": observed.get(field),
            })
    for field in numeric_fields:
        expected_value = expected[field]
        observed_value = observed.get(field)
        if expected_value is None:
            if observed_value is not None:
                issues.append({
                    "kind": "observed_null_mismatch", "location": location,
                    "field": field, "expected": None, "observed": observed_value,
                })
        elif not _observed_close(observed_value, _f(expected_value), atol, rtol):
            issues.append({
                "kind": "observed_numeric_mismatch", "location": location,
                "field": field, "expected": str(_f(expected_value)), "observed": observed_value,
            })
    return issues


def _close(observed: str | float, expected: F, atol: float, rtol: float) -> bool:
    observed_fraction = _f(observed)
    error = abs(float(observed_fraction - expected))
    return error <= atol + rtol * abs(float(expected))


def _case_oracle(parameters: dict[str, Any], policy: dict[str, Any], m_h: F | None = None) -> dict[str, F | bool]:
    p = {key: _f(value) for key, value in parameters.items()}
    fiscal = {key: _f(value) for key, value in policy["fiscal"].items()}
    mh = p["m_h"] if m_h is None else m_h
    ms = p["m_s"]
    tax = fiscal["tax_rate"] * fiscal["legal_coverage"] * fiscal["compliance"] * p["z"]
    admin = _f(policy["admin_cost"])
    transfer = _f(policy["transfer_h"])
    investment = _f(policy["investment_q"])
    reserve = _f(policy["reserve_b0"])
    operation = _f(policy["operation_x1"])
    reserve_1 = _f(policy["reserve_b1"])
    unused = _f(policy["unused_u0"])
    phi = _f(policy["phi"])
    income_h = p["income_h_0"] - p["z"] + transfer
    income_s = p["income_s_0"] + p["z"] - tax
    consumption_h = p["consumption_h_0"] + mh * (-p["z"] + transfer)
    consumption_s = p["consumption_s_0"] + ms * (p["z"] - tax)
    saving_h = income_h - consumption_h
    saving_s = income_s - consumption_s
    assets_h = p["assets_h_0"] + saving_h
    assets_s = p["assets_s_0"] + saving_s
    q_pre = (1 - p["delta_q"]) * p["q_0"] - p["damage_q"]
    q_raw = q_pre + phi * investment
    q_1 = _clip_unit(q_raw)
    service = min(p["a_operation"] * operation, p["b_capacity"] * q_1)
    opportunity = p["opportunity_0"] + p["rho_o"] * service
    direct = (
        -mh * p["z"] + ms * (p["z"] - tax) + mh * transfer
        + p["d_admin"] * admin + p["d_investment"] * investment
    )
    direct_from_uses = (
        consumption_h - p["consumption_h_0"]
        + consumption_s - p["consumption_s_0"]
        + p["d_admin"] * admin
        + p["d_investment"] * investment
    )
    return {
        "tax": tax,
        "net_public": tax - admin,
        "public_budget_residual": tax - admin - transfer - investment - reserve - unused,
        "reserve_budget_residual": p["reserve_return"] * reserve - operation - reserve_1,
        "income_h": income_h,
        "income_s": income_s,
        "consumption_h": consumption_h,
        "consumption_s": consumption_s,
        "saving_h": saving_h,
        "saving_s": saving_s,
        "assets_h": assets_h,
        "assets_s": assets_s,
        "household_h_residual": income_h - consumption_h - saving_h,
        "household_s_residual": income_s - consumption_s - saving_s,
        "q_pre": q_pre,
        "q_raw": q_raw,
        "q_1": q_1,
        "service": service,
        "opportunity": opportunity,
        "direct_demand": direct,
        "direct_demand_identity_residual": direct - direct_from_uses,
        "demand_gate": direct >= 0,
        "opportunity_gate": opportunity >= p["opportunity_min"],
    }


def _opportunity_minima(parameters: dict[str, Any], phi: F, opportunity_min: F | None = None) -> dict[str, Any]:
    p = {key: _f(value) for key, value in parameters.items()}
    target = p["opportunity_min"] if opportunity_min is None else opportunity_min
    required = max(F(0), (target - p["opportunity_0"]) / p["rho_o"])
    q_pre = (1 - p["delta_q"]) * p["q_0"] - p["damage_q"]
    if required == 0:
        return {"status": "already_satisfied", "s": F(0), "x": F(0), "q": F(0), "i": F(0), "b": F(0)}
    if required > p["b_capacity"]:
        return {"status": "technically_impossible", "s": required, "x": None, "q": None, "i": None, "b": None}
    operation = required / p["a_operation"]
    capacity = required / p["b_capacity"]
    investment = max(F(0), capacity - q_pre) / phi
    reserve = operation / p["reserve_return"]
    return {
        "status": "positive_feasible_target", "s": required,
        "x": operation, "q": capacity, "i": investment, "b": reserve,
    }


def _fixed_threshold_oracle(
    parameters: dict[str, Any],
    policy: dict[str, Any],
    opportunity_min: F | None = None,
) -> dict[str, Any]:
    """Derive both fixed-allocation thresholds from declared inputs."""
    p = {key: _f(value) for key, value in parameters.items()}
    fiscal = {key: _f(value) for key, value in policy["fiscal"].items()}
    tax = fiscal["tax_rate"] * fiscal["legal_coverage"] * fiscal["compliance"] * p["z"]
    transfer = _f(policy["transfer_h"])
    investment = _f(policy["investment_q"])
    operation = _f(policy["operation_x1"])
    displaced = p["z"] - transfer
    if displaced <= 0:
        raise ValueError("The independent threshold requires Z-y_T>0.")
    demand_constant = (
        p["m_s"] * (p["z"] - tax)
        + p["d_admin"] * _f(policy["admin_cost"])
        + p["d_investment"] * investment
    )
    demand_boundary = demand_constant / displaced
    target = p["opportunity_min"] if opportunity_min is None else opportunity_min
    service_required = max(F(0), (target - p["opportunity_0"]) / p["rho_o"])
    operation_ceiling = p["a_operation"] * operation
    q_pre = (1 - p["delta_q"]) * p["q_0"] - p["damage_q"]
    if service_required == 0:
        phi_boundary: F | None = F(0)
        required_capacity: F | None = F(0)
        status = "already_satisfied"
    elif service_required > p["b_capacity"]:
        phi_boundary = None
        required_capacity = None
        status = "technically_impossible"
    elif operation_ceiling < service_required:
        phi_boundary = None
        required_capacity = service_required / p["b_capacity"]
        status = "operation_insufficient"
    else:
        required_capacity = service_required / p["b_capacity"]
        gap = max(F(0), required_capacity - q_pre)
        if gap == 0:
            phi_boundary = F(0)
            status = "capacity_already_sufficient"
        elif investment == 0:
            phi_boundary = None
            status = "investment_insufficient"
        else:
            phi_boundary = gap / investment
            status = "interior_threshold"
    return {
        "demand_m_h_max": demand_boundary,
        "opportunity_phi_min": phi_boundary,
        "demand_constant": demand_constant,
        "displaced_net_of_transfer": displaced,
        "required_capacity": required_capacity,
        "preinvestment_capacity": q_pre,
        "service_required": service_required,
        "fixed_operation_service_ceiling": operation_ceiling,
        "opportunity_status": status,
    }


def _solve_linear(matrix: list[list[F]], vector: list[F]) -> list[F] | None:
    augmented = [list(row) + [value] for row, value in zip(matrix, vector, strict=True)]
    size = len(matrix)
    for column in range(size):
        pivot = next((row for row in range(column, size) if augmented[row][column]), None)
        if pivot is None:
            return None
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            scale = augmented[row][column]
            augmented[row] = [
                value - scale * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[column], strict=True)
            ]
    return [row[-1] for row in augmented]


def _enumerate_vertices(
    resources: F,
    investment_min: F,
    reserve_min: F,
    investment_cap: F | None,
) -> list[tuple[F, F, F]]:
    """Enumerate the full budget polytope, including B above its minimum."""
    budget = ([F(1), F(1), F(1)], resources)
    boundaries = [
        ([F(1), F(0), F(0)], F(0), "transfer_zero"),
        ([F(0), F(1), F(0)], investment_min, "investment_min"),
        ([F(0), F(0), F(1)], reserve_min, "reserve_min"),
    ]
    if investment_cap is not None:
        boundaries.append(([F(0), F(1), F(0)], investment_cap, "investment_cap"))
    vertices: list[tuple[F, F, F]] = []
    for first, second in combinations(boundaries, 2):
        solution = _solve_linear(
            [budget[0], first[0], second[0]],
            [budget[1], first[1], second[1]],
        )
        if solution is None:
            continue
        transfer, investment, reserve = solution
        cap_ok = investment_cap is None or investment <= investment_cap
        if transfer >= 0 and investment >= investment_min and reserve >= reserve_min and cap_ok:
            vertex = (transfer, investment, reserve)
            if vertex not in vertices:
                vertices.append(vertex)
    return sorted(vertices)


def _ledger_check(
    rows: list[dict[str, str]],
    scenario: str,
    case: dict[str, F | bool],
    policy: dict[str, Any],
    z: F,
) -> tuple[bool, dict[str, Any]]:
    p = policy
    amounts = {
        f"{scenario}-D0-AUTOMATION": z,
        f"{scenario}-D0-TAX": case["tax"],
        f"{scenario}-D0-TRANSFER": _f(p["transfer_h"]),
        f"{scenario}-D0-ADMIN": _f(p["admin_cost"]),
        f"{scenario}-D0-INVESTMENT": _f(p["investment_q"]),
        f"{scenario}-D0-RESERVE": _f(p["reserve_b0"]),
        f"{scenario}-D0-UNUSED": _f(p["unused_u0"]),
        f"{scenario}-D1-OPERATION": _f(p["operation_x1"]),
    }
    pairs = {
        f"{scenario}-D0-AUTOMATION": ("exposed_households_H", "owners_S"),
        f"{scenario}-D0-TAX": ("owners_S", "treasury"),
        f"{scenario}-D0-TRANSFER": ("treasury", "exposed_households_H"),
        f"{scenario}-D0-ADMIN": ("treasury", "administrative_supplier"),
        f"{scenario}-D0-INVESTMENT": ("treasury", "capital_goods_supplier"),
        f"{scenario}-D0-RESERVE": ("treasury", "depository"),
        f"{scenario}-D0-UNUSED": ("treasury", "depository"),
        f"{scenario}-D1-OPERATION": ("depository", "operating_input_supplier"),
    }
    problems: list[str] = []
    by_transaction: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_transaction.setdefault(row["transaction_id"], []).append(row)
        if row["unit"] != UNIT:
            problems.append(f"{row['entry_id']}:unit")
    for transaction, amount in amounts.items():
        group = by_transaction.get(transaction, [])
        if len(group) != 2:
            problems.append(f"{transaction}:entry_count")
            continue
        payer, receiver = pairs[transaction]
        payer_rows = [row for row in group if row["entry_role"] == "payer"]
        receiver_rows = [row for row in group if row["entry_role"] == "receiver"]
        if len(payer_rows) != 1 or len(receiver_rows) != 1:
            problems.append(f"{transaction}:roles")
            continue
        debit, credit = payer_rows[0], receiver_rows[0]
        if (debit["entity"], debit["counterparty"]) != (payer, receiver):
            problems.append(f"{transaction}:payer_counterparty")
        if (credit["entity"], credit["counterparty"]) != (receiver, payer):
            problems.append(f"{transaction}:receiver_counterparty")
        if _f(debit["cash_change"]) != -amount or _f(credit["cash_change"]) != amount:
            problems.append(f"{transaction}:cash_amount")
    balance_amounts = {
        f"{scenario}-D0-RESERVE-POSITION": _f(p["reserve_b0"]),
        f"{scenario}-D0-UNUSED-POSITION": _f(p["unused_u0"]),
        f"{scenario}-D1-RESERVE-REDEMPTION": -_f(p["operation_x1"]),
    }
    for transaction, amount in balance_amounts.items():
        group = by_transaction.get(transaction, [])
        assets = [row for row in group if row["entry_role"] == "asset"]
        liabilities = [row for row in group if row["entry_role"] == "liability"]
        if len(group) != 2 or len(assets) != 1 or len(liabilities) != 1:
            problems.append(f"{transaction}:deposit_pair")
            continue
        if (assets[0]["entity"], assets[0]["counterparty"]) != ("public_sector", "depository"):
            problems.append(f"{transaction}:asset_counterparty")
        if (liabilities[0]["entity"], liabilities[0]["counterparty"]) != ("depository", "public_sector"):
            problems.append(f"{transaction}:liability_counterparty")
        if _f(assets[0]["asset_change"]) != amount:
            problems.append(f"{transaction}:asset_obligation")
        if _f(liabilities[0]["liability_change"]) != amount:
            problems.append(f"{transaction}:liability_obligation")
    expected_ids = set(amounts) | set(balance_amounts)
    if set(by_transaction) != expected_ids:
        problems.append("transaction_inventory")
    if len(rows) != 22 or len({row["entry_id"] for row in rows}) != 22:
        problems.append("entry_inventory")
    return not problems, {"scenario": scenario, "entries": len(rows), "problems": problems}


def run_independent_checks(package_root: Path, run_root: Path) -> dict[str, Any]:
    package_root = package_root.resolve()
    run_root = run_root.resolve()
    benchmark = _read_decimal_json(package_root / "config" / "benchmark.json")
    scenarios_document = _read_decimal_json(package_root / "config" / "scenarios.json")
    tolerances = _read_decimal_json(package_root / "config" / "tolerances.json")["floating_point"]
    atol, rtol = float(tolerances["atol"]), float(tolerances["rtol"])
    parameters = benchmark["parameters"]
    policies = {item["name"]: item for item in scenarios_document["scenarios"]}
    policies["E"] = dict(policies["C"])
    policies["E"]["name"] = "E"
    observation_path = run_root / "independent" / "production_observations.json"
    production_observations, observation_document_issues = _safe_observations(observation_path)
    cases = {
        name: _case_oracle(parameters, policies[name], F(45, 100) if name == "E" else None)
        for name in "ABCDE"
    }
    checks: list[dict[str, Any]] = []

    def record(identifier: str, passed: bool, configurations: int, evidence: Any, scope: str = "appendix_A") -> None:
        checks.append({
            "id": identifier,
            "status": "passed" if passed else "failed",
            "configurations": configurations,
            "scope": scope,
            "evidence": evidence,
        })

    p = {key: _f(value) for key, value in parameters.items()}
    domains_ok = (
        p["omega_h"] + p["omega_s"] == 1
        and 0 <= p["m_s"] < p["m_h"] <= 1
        and p["p_0"] == p["p_1"] == p["reserve_return"] == 1
    )
    record("A01_declared_domains_and_units", domains_ok, 1, {
        "population_sum": str(p["omega_h"] + p["omega_s"]), "unit": UNIT,
    })

    account_failures: list[str] = []
    for name, case in cases.items():
        for field in (
            "public_budget_residual", "reserve_budget_residual", "household_h_residual",
            "household_s_residual", "direct_demand_identity_residual",
        ):
            if case[field] != 0:
                account_failures.append(f"{name}:{field}")
        for field in ("income_h", "income_s", "consumption_h", "consumption_s", "assets_h", "assets_s"):
            if case[field] < 0:
                account_failures.append(f"{name}:{field}:negative")
    record("A02_rational_household_public_accounts", not account_failures, 5, {
        "failures": account_failures,
        "accounts": {
            name: {key: str(value) for key, value in case.items() if isinstance(value, F)}
            for name, case in cases.items()
        },
    })

    scenario_rows = {row["scenario"]: row for row in _read_rows(run_root / "results" / "scenarios.csv")}
    scenario_rows["E"] = _read_rows(run_root / "results" / "constructive_case.csv")[0]
    case_failures: list[str] = []
    for name, case in cases.items():
        row = scenario_rows[name]
        for column, field in (("delta_D0_dir", "direct_demand"), ("q_1", "q_1"), ("service_1", "service"), ("O_1", "opportunity")):
            if not _close(row[column], case[field], atol, rtol):
                case_failures.append(f"{name}:{column}")
        if (row["demand_gate"] == "True") != case["demand_gate"]:
            case_failures.append(f"{name}:demand_gate")
        if (row["opportunity_gate"] == "True") != case["opportunity_gate"]:
            case_failures.append(f"{name}:opportunity_gate")
    record("A03_cases_A_to_E_exact_oracles", not case_failures, 5, {
        "failures": case_failures,
        "exact_values": {
            name: {
                "direct_demand": str(case["direct_demand"]),
                "opportunity": str(case["opportunity"]),
                "capacity": str(case["q_1"]),
                "gates": [case["demand_gate"], case["opportunity_gate"]],
            }
            for name, case in cases.items()
        },
        "float_comparison": {"atol": atol, "rtol": rtol},
    })

    ledger_rows = _read_rows(run_root / "results" / "ledger_entries.csv")
    constructive_ledger = _read_rows(run_root / "results" / "constructive_case_ledger_entries.csv")
    ledger_evidence = []
    for name in "ABCD":
        passed, evidence = _ledger_check(
            [row for row in ledger_rows if row["entry_id"].startswith(f"{name}-")],
            name, cases[name], policies[name], p["z"],
        )
        ledger_evidence.append({"passed": passed, **evidence})
    passed, evidence = _ledger_check(constructive_ledger, "E", cases["E"], policies["E"], p["z"])
    ledger_evidence.append({"passed": passed, **evidence})
    record("A04_rational_ledger_counterparties_and_deposits", all(item["passed"] for item in ledger_evidence), 110, ledger_evidence)

    c = policies["C"]
    fixed_expected = _fixed_threshold_oracle(parameters, c)
    mh_boundary = fixed_expected["demand_m_h_max"]
    phi_boundary = fixed_expected["opportunity_phi_min"]
    if phi_boundary is None:
        raise AssertionError("The benchmark fixed-allocation capacity boundary must be finite.")
    demand_at = _case_oracle(parameters, c, mh_boundary)["direct_demand"]
    phi_policy = dict(c)
    phi_policy["phi"] = phi_boundary
    opportunity_at = _case_oracle(parameters, phi_policy)["opportunity"]
    epsilon = F(1, 1000)
    demand_below = _case_oracle(parameters, c, mh_boundary - epsilon)["direct_demand"]
    demand_above = _case_oracle(parameters, c, mh_boundary + epsilon)["direct_demand"]
    phi_below_policy, phi_above_policy = dict(c), dict(c)
    phi_below_policy["phi"] = phi_boundary - epsilon
    phi_above_policy["phi"] = phi_boundary + epsilon
    opportunity_below = _case_oracle(parameters, phi_below_policy)["opportunity"]
    opportunity_above = _case_oracle(parameters, phi_above_policy)["opportunity"]
    fixed_rows, fixed_file_issues = _safe_rows(
        run_root / "results" / "fixed_policy_gate_thresholds.csv"
    )
    fixed_row_expected = [{
        key: value for key, value in fixed_expected.items()
    }]
    fixed_comparison_issues = _compare_rows(
        "fixed_policy_gate_thresholds.csv",
        fixed_rows,
        fixed_row_expected,
        (),
        (
            "demand_m_h_max", "opportunity_phi_min", "demand_constant",
            "displaced_net_of_transfer", "required_capacity",
            "preinvestment_capacity", "service_required",
            "fixed_operation_service_ceiling",
        ),
        ("opportunity_status",),
        atol,
        rtol,
    ) if not fixed_file_issues else []
    frontier_ok = (
        demand_at == 0 and demand_below > 0 and demand_above < 0
        and opportunity_at == p["opportunity_min"]
        and opportunity_below < p["opportunity_min"]
        and opportunity_above >= p["opportunity_min"]
        and not fixed_file_issues and not fixed_comparison_issues
    )
    record("A05_exact_frontiers_and_inclusive_boundaries", frontier_ok, 6, {
        "m_H_star": str(mh_boundary), "phi_star": str(phi_boundary),
        "demand": list(map(str, (demand_below, demand_at, demand_above))),
        "opportunity": list(map(str, (opportunity_below, opportunity_at, opportunity_above))),
        "epsilon": str(epsilon), "equalities_pass": True,
        "inputs_used": ["config/benchmark.json", "config/scenarios.json:scenario C"],
        "observed_output": "results/fixed_policy_gate_thresholds.csv",
        "comparison_performed": "derived fields, row key, status and written numeric values",
        "issues": [*fixed_file_issues, *fixed_comparison_issues],
        "coverage_units": {"boundary_sample_points": 6, "written_output_rows": len(fixed_rows)},
    })

    projection_inputs = [F(-2), F(-1, 10), F(0), F(1, 2), F(1), F(3, 2)]
    projection_expected = [_clip_unit(value) for value in projection_inputs]
    projection_issues = list(observation_document_issues)
    projection_observed = production_observations.get("projection")
    if not isinstance(projection_observed, list) or len(projection_observed) != len(projection_inputs):
        projection_issues.append({
            "kind": "observed_case_count", "location": "production_observations.json:projection",
            "expected": len(projection_inputs),
            "observed": len(projection_observed) if isinstance(projection_observed, list) else None,
        })
    else:
        for index, (input_value, expected_value, observed) in enumerate(
            zip(projection_inputs, projection_expected, projection_observed, strict=True)
        ):
            projection_issues.extend(_compare_mapping(
                f"production_observations.json:projection[{index}]",
                observed,
                {"input": input_value, "projected": expected_value},
                ("input", "projected"),
                (),
                atol,
                rtol,
            ))
    projection_ok = (
        projection_expected == [F(0), F(0), F(0), F(1, 2), F(1), F(1)]
        and not projection_issues
    )
    record("A06_capacity_projection_corners", projection_ok, len(projection_inputs), {
        "inputs": list(map(str, projection_inputs)),
        "expected_outputs": list(map(str, projection_expected)),
        "observed_output": "independent/production_observations.json:projection",
        "comparison_performed": "six expected projections versus six production observations",
        "issues": projection_issues,
        "coverage_units": {"projection_points": len(projection_inputs)},
    })

    minima = _opportunity_minima(parameters, p["phi_high"])
    already = _opportunity_minima(parameters, p["phi_high"], p["opportunity_0"])
    impossible = _opportunity_minima(parameters, p["phi_high"], p["opportunity_0"] + p["rho_o"] * (p["b_capacity"] + 1))
    analytical_expected: list[dict[str, Any]] = []
    analytical_settings = benchmark["generation"]["analytical"]
    phi_cases = {"high": p["phi_high"], "low": p["phi_low"]}
    for capacity_case in analytical_settings["capacity_cases"]:
        phi = phi_cases[capacity_case]
        requirement = _opportunity_minima(parameters, phi)
        for transfer_value in analytical_settings["fixed_transfers"]:
            transfer = _f(transfer_value)
            finance = transfer + requirement["i"] + requirement["b"]
            available = _f(analytical_settings["available_net_resources"])
            analytical_expected.append({
                "capacity_case": capacity_case,
                "phi": phi,
                "target_case": requirement["status"],
                "s_required": requirement["s"],
                "X_min": requirement["x"],
                "q_required": requirement["q"],
                "I_min": requirement["i"],
                "B_min": requirement["b"],
                "fixed_transfer": transfer,
                "minimum_date0_finance": finance,
                "available_net_resources": available,
                "fiscally_feasible": finance <= available,
            })
    analytical_rows_observed, analytical_file_issues = _safe_rows(
        run_root / "results" / "analytical_conditions.csv"
    )
    analytical_comparison_issues = _compare_rows(
        "analytical_conditions.csv",
        analytical_rows_observed,
        analytical_expected,
        ("capacity_case", "fixed_transfer"),
        (
            "phi", "s_required", "X_min", "q_required", "I_min", "B_min",
            "fixed_transfer", "minimum_date0_finance", "available_net_resources",
        ),
        ("target_case", "fiscally_feasible"),
        atol,
        rtol,
    ) if not analytical_file_issues else []
    requirement_issues = list(observation_document_issues)
    observed_requirements = production_observations.get("opportunity_requirements", {})
    requirement_fields = (
        "service_required", "operation_min", "capacity_min", "investment_min", "reserve_min"
    )
    requirement_map = {
        "positive": minima,
        "already_satisfied": already,
        "technically_impossible": impossible,
    }
    for label, expected in requirement_map.items():
        expected_observation = {
            "status": expected["status"],
            "service_required": expected["s"],
            "operation_min": expected["x"],
            "capacity_min": expected["q"],
            "investment_min": expected["i"],
            "reserve_min": expected["b"],
        }
        requirement_issues.extend(_compare_mapping(
            f"production_observations.json:opportunity_requirements.{label}",
            observed_requirements.get(label) if isinstance(observed_requirements, dict) else None,
            expected_observation,
            requirement_fields,
            ("status",),
            atol,
            rtol,
        ))
    minima_ok = (
        minima["s"] == 4 and minima["x"] == 4 and minima["q"] == F(4, 5)
        and minima["i"] == F(73, 25) and minima["b"] == 4
        and already["status"] == "already_satisfied" and already["i"] == 0
        and impossible["status"] == "technically_impossible" and impossible["i"] is None
        and not analytical_file_issues and not analytical_comparison_issues and not requirement_issues
    )
    record("A07_minima_already_satisfied_and_ceiling", minima_ok, 3, {
        "positive": {key: None if value is None else str(value) for key, value in minima.items()},
        "already_satisfied": {key: None if value is None else str(value) for key, value in already.items()},
        "impossible": {key: None if value is None else str(value) for key, value in impossible.items()},
        "inputs_used": ["config/benchmark.json:generation.analytical", "config/benchmark.json:parameters"],
        "observed_outputs": [
            "results/analytical_conditions.csv",
            "independent/production_observations.json:opportunity_requirements",
        ],
        "comparison_performed": "four written analytical rows plus three production edge observations",
        "issues": [*analytical_file_issues, *analytical_comparison_issues, *requirement_issues],
        "coverage_units": {
            "opportunity_requirement_cases": 3,
            "written_analytical_rows": len(analytical_rows_observed),
        },
    })

    saturated_service_with_low_operation = min(F(3), p["b_capacity"] * _clip_unit(F(100)))
    operation_opportunity = p["opportunity_0"] + p["rho_o"] * saturated_service_with_low_operation
    operation_investment = (1 - fixed_expected["preinvestment_capacity"]) / p["phi_high"]
    operation_resources = (
        _f(c["fiscal"]["tax_rate"])
        * _f(c["fiscal"]["legal_coverage"])
        * _f(c["fiscal"]["compliance"])
        * p["z"]
        - _f(c["admin_cost"])
    )
    operation_expected = _fixed_threshold_oracle(
        parameters,
        {
            **c,
            "transfer_h": operation_resources - operation_investment - F(3),
            "investment_q": operation_investment,
            "reserve_b0": 3,
            "operation_x1": 3,
            "reserve_b1": 0,
            "unused_u0": 0,
        },
    )
    operation_issues = list(observation_document_issues)
    operation_observed = production_observations.get("operation_insufficient", {})
    operation_issues.extend(_compare_mapping(
        "production_observations.json:operation_insufficient.threshold",
        operation_observed.get("threshold") if isinstance(operation_observed, dict) else None,
        {
            "opportunity_status": operation_expected["opportunity_status"],
            "opportunity_phi_min": operation_expected["opportunity_phi_min"],
            "required_capacity": operation_expected["required_capacity"],
            "service_required": operation_expected["service_required"],
            "fixed_operation_service_ceiling": operation_expected["fixed_operation_service_ceiling"],
        },
        (
            "opportunity_phi_min", "required_capacity", "service_required",
            "fixed_operation_service_ceiling",
        ),
        ("opportunity_status",),
        atol,
        rtol,
    ))
    operation_issues.extend(_compare_mapping(
        "production_observations.json:operation_insufficient.scenario",
        operation_observed.get("scenario") if isinstance(operation_observed, dict) else None,
        {
            "q_1": F(1),
            "service_1": F(3),
            "opportunity_1": operation_opportunity,
            "opportunity_gate": False,
        },
        ("q_1", "service_1", "opportunity_1"),
        ("opportunity_gate",),
        atol,
        rtol,
    ))
    operation_ok = (
        operation_opportunity < p["opportunity_min"]
        and operation_expected["opportunity_status"] == "operation_insufficient"
        and not operation_issues
    )
    record("A08_operation_insufficient_at_capacity_ceiling", operation_ok, 1, {
        "operation": "3", "capacity": "1",
        "expected_opportunity": str(operation_opportunity),
        "observed_output": "independent/production_observations.json:operation_insufficient",
        "comparison_performed": "derived operation-insufficient status and scenario values versus production adapter",
        "issues": operation_issues,
        "coverage_units": {"operation_insufficient_cases": 1},
    })

    capture_zero = cases["A"]
    finance_shortfall = F(6) < minima["i"] + minima["b"]
    fiscal_issues = list(observation_document_issues)
    fiscal_observed = production_observations.get("fiscal_edge_cases", {})
    fiscal_issues.extend(_compare_mapping(
        "production_observations.json:fiscal_edge_cases.zero_capture",
        fiscal_observed.get("zero_capture") if isinstance(fiscal_observed, dict) else None,
        {"tax": F(0), "delta_demand_0": F(-12), "demand_gate": False},
        ("tax", "delta_demand_0"),
        ("demand_gate",),
        atol,
        rtol,
    ))
    fiscal_issues.extend(_compare_mapping(
        "production_observations.json:fiscal_edge_cases.finance_shortfall",
        fiscal_observed.get("finance_shortfall") if isinstance(fiscal_observed, dict) else None,
        {
            "feasible": False,
            "status": "fiscally_infeasible",
            "delta_demand_max": None,
            "minimum_total": minima["i"] + minima["b"],
            "resources": F(6),
        },
        ("delta_demand_max", "minimum_total", "resources"),
        ("feasible", "status"),
        atol,
        rtol,
    ))
    record("A09_zero_capture_and_finance_shortfall", (
        capture_zero["tax"] == 0
        and capture_zero["direct_demand"] == -12
        and finance_shortfall
        and not fiscal_issues
    ), 2, {
        "zero_capture_direct_demand": str(capture_zero["direct_demand"]),
        "minimum_finance": str(minima["i"] + minima["b"]), "test_resources": "6",
        "observed_output": "independent/production_observations.json:fiscal_edge_cases",
        "comparison_performed": "derived zero-capture and fiscal-shortfall outcomes versus production adapter",
        "issues": fiscal_issues,
        "coverage_units": {"fiscal_edge_cases": 2},
    })

    resources = cases["C"]["net_public"]
    investment_min = minima["i"]
    reserve_min = minima["b"]
    q_pre = minima["q"] - p["phi_high"] * investment_min
    investment_cap = (1 - q_pre) / p["phi_high"]
    base = -p["m_h"] * p["z"] + p["m_s"] * (p["z"] - cases["C"]["tax"]) + p["d_admin"] * _f(c["admin_cost"])
    vertices_capped = _enumerate_vertices(resources, investment_min, reserve_min, investment_cap)
    vertices_uncapped = _enumerate_vertices(resources, investment_min, reserve_min, None)

    def objective(vertex: tuple[F, F, F], d_i: F = p["d_investment"]) -> F:
        transfer, investment, _reserve = vertex
        return base + p["m_h"] * transfer + d_i * investment

    optimum_capped = max((objective(vertex), vertex) for vertex in vertices_capped)
    optimum_uncapped = max((objective(vertex), vertex) for vertex in vertices_uncapped)
    optimization_expected = [
        {
            "case": "productive_investment_ceiling",
            "delta_demand_max": optimum_capped[0],
            "investment": optimum_capped[1][1],
            "transfer": optimum_capped[1][0],
            "reserve": optimum_capped[1][2],
            "opportunity_floor_financed": True,
            "unit": UNIT,
        },
        {
            "case": "no_productive_investment_ceiling",
            "delta_demand_max": optimum_uncapped[0],
            "investment": optimum_uncapped[1][1],
            "transfer": optimum_uncapped[1][0],
            "reserve": optimum_uncapped[1][2],
            "opportunity_floor_financed": True,
            "unit": UNIT,
        },
    ]
    optimization_observed, optimization_file_issues = _safe_rows(
        run_root / "results" / "optimization_summary.csv"
    )
    optimization_comparison_issues = _compare_rows(
        "optimization_summary.csv",
        optimization_observed,
        optimization_expected,
        ("case",),
        ("delta_demand_max", "investment", "transfer", "reserve"),
        ("opportunity_floor_financed", "unit"),
        atol,
        rtol,
    ) if not optimization_file_issues else []
    feasibility_issues: list[dict[str, Any]] = []
    for regime, vertices, cap in (
        ("productive_investment_ceiling", vertices_capped, investment_cap),
        ("no_productive_investment_ceiling", vertices_uncapped, None),
    ):
        for vertex in vertices:
            transfer, investment, reserve = vertex
            if transfer + investment + reserve != resources:
                feasibility_issues.append({"kind": "budget", "regime": regime, "vertex": list(map(str, vertex))})
            if transfer < 0 or investment < investment_min or reserve < reserve_min:
                feasibility_issues.append({"kind": "allocation_domain", "regime": regime, "vertex": list(map(str, vertex))})
            if cap is not None and investment > cap:
                feasibility_issues.append({"kind": "productive_cap", "regime": regime, "vertex": list(map(str, vertex))})
            vertex_policy = {
                **c,
                "transfer_h": transfer,
                "investment_q": investment,
                "reserve_b0": reserve,
                "operation_x1": reserve_min,
                "reserve_b1": reserve - reserve_min,
                "unused_u0": 0,
                "phi": p["phi_high"],
            }
            vertex_case = _case_oracle(parameters, vertex_policy)
            for field in ("consumption_h", "consumption_s", "assets_h", "assets_s"):
                if vertex_case[field] < 0:
                    feasibility_issues.append({
                        "kind": "household_constraint", "regime": regime,
                        "vertex": list(map(str, vertex)), "field": field,
                        "value": str(vertex_case[field]),
                    })
    benchmark_controls = {
        "capped_value": optimum_capped[0] == F(-391, 125),
        "capped_allocation": optimum_capped[1] == (F(282, 25), F(93, 25), F(4)),
        "uncapped_value": optimum_uncapped[0] == -2,
        "uncapped_allocation": optimum_uncapped[1] == (F(0), F(15), F(4)),
    }
    vertex_ok = (
        all(benchmark_controls.values())
        and not optimization_file_issues
        and not optimization_comparison_issues
        and not feasibility_issues
    )
    optimization_vertex_count = len(vertices_capped) + len(vertices_uncapped)
    record("A10_vertex_enumeration_with_and_without_cap", vertex_ok, optimization_vertex_count, {
        "capped_vertices": [[str(value) for value in vertex] for vertex in vertices_capped],
        "uncapped_vertices": [[str(value) for value in vertex] for vertex in vertices_uncapped],
        "capped_optimum": str(optimum_capped[0]), "uncapped_optimum": str(optimum_uncapped[0]),
        "inputs_used": ["config/benchmark.json:parameters", "config/benchmark.json:generation.fixed_allocation"],
        "observed_output": "results/optimization_summary.csv",
        "comparison_performed": "derived optima and allocations versus both written rows",
        "full_budget_enumerated": True,
        "reserve_minimum_reduction": (
            "The full polytope is enumerated. Because m_H>0 and d_I>0 while reserve "
            "has no direct-demand coefficient, an optimum uses B=B_min."
        ),
        "household_constraints_checked": ["consumption_h", "consumption_s", "assets_h_1", "assets_s_1"],
        "benchmark_controls": benchmark_controls,
        "issues": [*optimization_file_issues, *optimization_comparison_issues, *feasibility_issues],
        "coverage_units": {
            "capped_vertices": len(vertices_capped),
            "uncapped_vertices": len(vertices_uncapped),
            "written_optimization_rows": len(optimization_observed),
        },
    })

    fixed_reserve_vertices = [
        vertex for vertex in vertices_capped if vertex[2] == reserve_min
    ]
    equal_values = {objective(vertex, p["m_h"]) for vertex in fixed_reserve_vertices}
    constant_expected_allocations = [
        ("minimum_investment", resources - investment_min - reserve_min, investment_min, reserve_min),
        ("maximum_investment_without_cap", F(0), resources - reserve_min, reserve_min),
    ]
    constant_issues = list(observation_document_issues)
    constant_observed = production_observations.get("constant_objective", {})
    constant_issues.extend(_compare_mapping(
        "production_observations.json:constant_objective",
        constant_observed,
        {"d_investment": p["m_h"], "m_h": p["m_h"]},
        ("d_investment", "m_h"),
        (),
        atol,
        rtol,
    ))
    observed_allocations = constant_observed.get("observations", []) if isinstance(constant_observed, dict) else []
    observed_by_name = {
        item.get("name"): item for item in observed_allocations if isinstance(item, dict)
    }
    equal_parameters = dict(parameters)
    equal_parameters["d_investment"] = p["m_h"]
    expected_constant_values: set[F] = set()
    for name, transfer, investment, reserve in constant_expected_allocations:
        equal_policy = {
            **c,
            "transfer_h": transfer,
            "investment_q": investment,
            "reserve_b0": reserve,
            "operation_x1": reserve_min,
            "reserve_b1": reserve - reserve_min,
            "unused_u0": 0,
        }
        expected_case = _case_oracle(equal_parameters, equal_policy)
        expected_constant_values.add(expected_case["direct_demand"])
        constant_issues.extend(_compare_mapping(
            f"production_observations.json:constant_objective.{name}",
            observed_by_name.get(name),
            {
                "transfer": transfer,
                "investment": investment,
                "reserve": reserve,
                "direct_demand": expected_case["direct_demand"],
                "consumption_h": expected_case["consumption_h"],
                "consumption_s": expected_case["consumption_s"],
                "assets_h_1": expected_case["assets_h"],
                "assets_s_1": expected_case["assets_s"],
            },
            (
                "transfer", "investment", "reserve", "direct_demand",
                "consumption_h", "consumption_s", "assets_h_1", "assets_s_1",
            ),
            (),
            atol,
            rtol,
        ))
    record("A11_constant_objective_equal_coefficients", (
        len(equal_values) == 1
        and len(expected_constant_values) == 1
        and not constant_issues
    ), len(constant_expected_allocations), {
        "d_I": str(p["m_h"]), "objective_values": sorted(map(str, equal_values)),
        "reserve_fixed_at_minimum": str(reserve_min),
        "observed_output": "independent/production_observations.json:constant_objective",
        "comparison_performed": "two fixed-reserve allocations versus production direct-demand observations",
        "scope_condition": "The objective is constant over transfer-investment reallocations only while B=B_min is fixed.",
        "issues": constant_issues,
        "coverage_units": {"fixed_reserve_allocations": len(constant_expected_allocations)},
    })

    threshold = p["m_h"] - p["m_s"]
    finite_policies = [(F(k, 4), F(d, 4)) for k in range(3) for d in range(5)]
    gamma = max(kappa * (coefficient - p["m_s"]) for kappa, coefficient in finite_policies)
    direct_values = [-(p["m_h"] - p["m_s"]) + kappa * (coefficient - p["m_s"]) for kappa, coefficient in finite_policies]
    no_go_ok = gamma < threshold and all(value < 0 for value in direct_values)
    record("C16_01_collection_execution_bound", no_go_ok, len(finite_policies), {
        "label": "prop:collection_execution_no_go_ch16",
        "finite_envelope": str(gamma), "threshold": str(threshold),
        "maximum_direct_demand_per_Z": str(max(direct_values)),
    }, "chapter_16_finite_complement")

    m_d, kappa_d = F(1), F(9, 10)
    demand_only = -threshold + kappa_d * (m_d - p["m_s"])
    kappa_o = F(1, 2)
    opportunity_only_upper = -threshold + kappa_o * (1 - p["m_s"])
    separation_ok = (
        demand_only >= 0 and p["opportunity_0"] < p["opportunity_min"]
        and opportunity_only_upper < 0 and p["opportunity_0"] + 4 >= p["opportunity_min"]
    )
    record("C16_02_constructive_two_gate_separation", separation_ok, 2, {
        "label": "prop:two_gate_separation_ch16",
        "demand_only": str(demand_only), "opportunity_baseline": str(p["opportunity_0"]),
        "opportunity_only_demand_upper": str(opportunity_only_upper), "opportunity_witness": "5",
        "assumptions": {
            "both_allocations_admissible": True,
            "demand_witness": {
                "execution_mpc": str(m_d),
                "capture_fraction": str(kappa_d),
                "opportunity_remains_at_baseline": True,
            },
            "opportunity_witness": {
                "capture_fraction": str(kappa_o),
                "admissible_conversion_to_O_equal_5": "assumed for the finite witness",
                "conversion_estimated_or_calculated_here": False,
            },
        },
        "scope_warning": (
            "The opportunity outcome is an admissible witness assumed for this finite "
            "non-equivalence example; it is not an estimated conversion technology."
        ),
    }, "chapter_16_finite_complement")

    matrix = ((F(7, 10), F(1, 10)), (F(1, 10), F(6, 10)))
    seed = (F(2, 100), F(1, 100))
    upper = (F(1, 5), F(1, 5))
    primitive_condition = all(
        seed[i] + sum(matrix[i][j] * upper[j] for j in range(2)) <= upper[i]
        for i in range(2)
    )
    invariant = True
    invariant_configurations = 0
    for qa, qb in product(range(21), repeat=2):
        state = (F(qa, 100), F(qb, 100))
        for damage in ((F(0), F(0)), (F(1), F(0)), (F(0), F(1)), (F(1), F(1))):
            next_state = tuple(
                _clip_unit(seed[i] + sum(matrix[i][j] * state[j] for j in range(2)) - damage[i])
                for i in range(2)
            )
            invariant = invariant and all(0 <= next_state[i] <= upper[i] for i in range(2))
            invariant_configurations += 1
    record("C16_03_primitive_capacity_trap_finite_check", primitive_condition and invariant, invariant_configurations, {
        "label": "prop:primitive_capacity_trap_ch16",
        "upper_box": list(map(str, upper)), "primitive_condition": primitive_condition,
        "projection_order_preserving": True, "damage_values_nonnegative": True,
    }, "chapter_16_finite_complement")

    failures = [check for check in checks if check["status"] != "passed"]
    heterogeneous_units_total = sum(check["configurations"] for check in checks)
    coverage_counts = {
        "declared_domain_sets": 1,
        "scenario_account_cases": 5,
        "scenario_output_cases": 5,
        "ledger_entries": 110,
        "boundary_sample_points": 6,
        "fixed_policy_output_rows": len(fixed_rows),
        "projection_points": len(projection_inputs),
        "opportunity_requirement_cases": 3,
        "analytical_output_rows": len(analytical_rows_observed),
        "operation_insufficient_cases": 1,
        "fiscal_edge_cases": 2,
        "optimization_vertices": optimization_vertex_count,
        "optimization_output_rows": len(optimization_observed),
        "constant_objective_allocations": len(constant_expected_allocations),
        "chapter16_policy_pairs": len(finite_policies),
        "chapter16_constructive_witnesses": 2,
        "chapter16_state_damage_pairs": invariant_configurations,
    }
    return {
        "schema_version": 2,
        "stage": "P3_independent_oracles",
        "status": "passed" if not failures else "failed",
        "oracle_separation": {
            "production_module_imported": False,
            "production_functions_called": [],
            "expected_side": (
                "declared JSON inputs, rational derivations and independently enumerated vertices; "
                "no production-model import or function call"
            ),
            "observed_side": (
                "written product CSV files plus production_observations.json created by the "
                "separate adapter"
            ),
            "shared_material": "declared JSON inputs and written outputs only",
            "arithmetic": "fractions constructed from decimal JSON tokens and integer ratios",
        },
        "scope_notice": (
            "These exact and finite checks complement the analytical proofs. They are not a "
            "proof of the three general Chapter 16 results and do not solve the parent HANK equilibrium."
        ),
        "boundary_convention": {
            "demand_gate": "delta_D >= 0; equality passes",
            "opportunity_gate": "O >= O_min; equality passes",
            "float_output_tolerances": {"atol": atol, "rtol": rtol},
            "valid_nonfinite_state": "represented by a named status and null minima, never an unexpected CSV NaN/Infinity",
        },
        "groups_total": len(checks),
        "groups_passed": len(checks) - len(failures),
        "groups_failed": len(failures),
        "configurations_checked": heterogeneous_units_total,
        "heterogeneous_units_total": heterogeneous_units_total,
        "count_notice": (
            "This aggregate combines ledger entries, scenario cases, boundary points, "
            "optimization vertices, finite policy witnesses and state-damage grid pairs. "
            "It is not a count of independent production-model economies."
        ),
        "coverage_counts_by_unit": coverage_counts,
        "checks": checks,
        "scientific_discrepancies": [],
    }
