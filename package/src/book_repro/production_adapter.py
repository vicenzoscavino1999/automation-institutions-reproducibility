"""Observe declared edge cases through the production model for P3 comparison.

This module is deliberately separate from :mod:`book_repro.independent`.  It
may call production functions to obtain the observed side of a comparison;
the independent module derives the expected side without importing this module
or ``book_repro.model``.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from .model import (
    Parameters,
    Policy,
    compute_scenario,
    direct_demand_formula,
    fixed_allocation_gate_thresholds,
    maximum_joint_demand,
    opportunity_requirement,
    project_unit,
)


def _finite_or_none(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _serializable_dataclass(value: Any) -> dict[str, Any]:
    return {key: _finite_or_none(item) for key, item in asdict(value).items()}


def build_production_observations(
    parameters: Parameters,
    policies: list[Policy],
) -> dict[str, Any]:
    """Evaluate edge cases with the production implementation."""
    policy_by_name = {policy.name: policy for policy in policies}
    policy_a = policy_by_name["A"]
    policy_c = policy_by_name["C"]

    projection_inputs = [-2.0, -0.1, 0.0, 0.5, 1.0, 1.5]
    projection = [
        {"input": value, "projected": project_unit(value)}
        for value in projection_inputs
    ]

    positive = opportunity_requirement(parameters, parameters.phi_high)
    already_parameters = replace(
        parameters,
        opportunity_min=parameters.opportunity_0,
    )
    already = opportunity_requirement(already_parameters, parameters.phi_high)
    impossible_parameters = replace(
        parameters,
        opportunity_min=(
            parameters.opportunity_0
            + parameters.rho_o * (parameters.b_capacity + 1.0)
        ),
    )
    impossible = opportunity_requirement(impossible_parameters, parameters.phi_high)

    productive_investment_cap = (
        1.0 - parameters.q_preinvestment
    ) / parameters.phi_high
    operation_probe_reserve = 3.0
    operation_limited_policy = replace(
        policy_c,
        name="operation_insufficient_probe",
        description="P3 production observation: operation is below the service requirement",
        transfer_h=(
            policy_c.tax(parameters)
            - policy_c.admin_cost
            - productive_investment_cap
            - operation_probe_reserve
        ),
        investment_q=productive_investment_cap,
        reserve_b0=operation_probe_reserve,
        operation_x1=3.0,
        reserve_b1=0.0,
        unused_u0=0.0,
    )
    operation_threshold = fixed_allocation_gate_thresholds(
        parameters,
        operation_limited_policy,
    )
    operation_scenario = compute_scenario(parameters, operation_limited_policy)

    zero_capture = compute_scenario(parameters, policy_a)
    finance_shortfall = maximum_joint_demand(
        parameters,
        tax_rate=0.35,
        admin_cost=1.0,
        phi=parameters.phi_high,
        legal_coverage=1.0,
        compliance=1.0,
    )

    equal_parameters = replace(parameters, d_investment=parameters.m_h)
    resources = policy_c.tax(parameters) - policy_c.admin_cost
    constant_allocations = [
        (
            "minimum_investment",
            resources - positive.investment_min - positive.reserve_min,
            positive.investment_min,
            positive.reserve_min,
        ),
        (
            "maximum_investment_without_cap",
            0.0,
            resources - positive.reserve_min,
            positive.reserve_min,
        ),
    ]
    constant_objective = []
    for name, transfer, investment, reserve in constant_allocations:
        policy = replace(
            policy_c,
            name=name,
            description="P3 production observation: equal transfer and investment coefficients",
            transfer_h=transfer,
            investment_q=investment,
            reserve_b0=reserve,
            operation_x1=4.0,
            reserve_b1=reserve - 4.0,
            unused_u0=0.0,
        )
        result = compute_scenario(equal_parameters, policy)
        constant_objective.append({
            "name": name,
            "transfer": transfer,
            "investment": investment,
            "reserve": reserve,
            "direct_demand": direct_demand_formula(equal_parameters, policy),
            "consumption_h": result.consumption_h,
            "consumption_s": result.consumption_s,
            "assets_h_1": result.assets_h_1,
            "assets_s_1": result.assets_s_1,
        })

    return {
        "schema_version": 1,
        "stage": "P3_production_observation_adapter",
        "adapter_scope": (
            "Observed side only. Independent expected values are derived in "
            "book_repro.independent without calling these functions."
        ),
        "production_functions_called": [
            "project_unit",
            "opportunity_requirement",
            "fixed_allocation_gate_thresholds",
            "compute_scenario",
            "maximum_joint_demand",
            "direct_demand_formula",
        ],
        "projection": projection,
        "opportunity_requirements": {
            "positive": _serializable_dataclass(positive),
            "already_satisfied": _serializable_dataclass(already),
            "technically_impossible": _serializable_dataclass(impossible),
        },
        "operation_insufficient": {
            "threshold": _serializable_dataclass(operation_threshold),
            "scenario": {
                "q_raw_1": operation_scenario.q_raw_1,
                "q_1": operation_scenario.q_1,
                "service_1": operation_scenario.service_1,
                "opportunity_1": operation_scenario.opportunity_1,
                "opportunity_gate": operation_scenario.opportunity_gate,
            },
        },
        "fiscal_edge_cases": {
            "zero_capture": {
                "tax": zero_capture.tax,
                "delta_demand_0": zero_capture.delta_demand_0,
                "demand_gate": zero_capture.demand_gate,
            },
            "finance_shortfall": {
                key: _finite_or_none(value)
                for key, value in finance_shortfall.items()
            },
        },
        "constant_objective": {
            "d_investment": equal_parameters.d_investment,
            "m_h": equal_parameters.m_h,
            "reserve_condition": "B is fixed at the minimum B_min=4",
            "observations": constant_objective,
        },
    }


def write_production_observations(
    run_root: Path,
    parameters: Parameters,
    policies: list[Policy],
) -> Path:
    """Write the production-observation side before independent comparison."""
    path = run_root.resolve() / "independent" / "production_observations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = build_production_observations(parameters, policies)
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return path
