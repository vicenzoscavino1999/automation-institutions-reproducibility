"""Generate reduced-economy results without consulting frozen references."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import sys
from dataclasses import asdict, replace
from pathlib import Path

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors

from .model import (
    FiscalInstrument,
    Parameters,
    Policy,
    build_ledger,
    compute_scenario,
    fixed_allocation_gate_thresholds,
    ledger_checks,
    maximum_joint_demand,
    opportunity_requirement,
)


RESULTS: Path
FIGURES: Path
PROVENANCE: Path


def linspace(start: float, stop: float, count: int) -> list[float]:
    if count < 2:
        return [start]
    step = (stop - start) / (count - 1)
    return [start + i * step for i in range(count)]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        if not rows:
            raise ValueError(f"Cannot infer columns for empty output: {path}")
        fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: float, digits: int = 3) -> str:
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if math.isnan(value):
        return "NA"
    return f"{value:.{digits}f}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_provenance_manifest() -> dict:
    return json.loads(PROVENANCE.read_text(encoding="utf-8"))


def verify_external_provenance(manifest: dict, external_root: Path | None) -> dict:
    """Optionally compare recorded hashes with a separate parent-project path."""
    if external_root is None:
        return {"status": "not_requested", "root": None, "sources": []}
    root = external_root.resolve()
    checked = []
    for source in manifest["sources"]:
        path = root / Path(source["relative_path"])
        if not path.is_file():
            raise FileNotFoundError(f"Provenance source not found: {path}")
        observed = sha256(path)
        expected = source["sha256"]
        if observed != expected:
            raise AssertionError(
                f"Provenance mismatch for {source['id']}: expected {expected}, observed {observed}"
            )
        checked.append({"id": source["id"], "relative_path": source["relative_path"],
                        "sha256": observed, "status": "match"})
    return {"status": "verified", "root": str(root), "sources": checked}


def parameter_rows(p: Parameters) -> list[dict]:
    return [
        {"symbol": "omega_H", "value": p.omega_h, "unit": "population share", "interpretation": "Exposed households", "selection_rule": "Two-group unit-mass normalization"},
        {"symbol": "omega_S", "value": p.omega_s, "unit": "population share", "interpretation": "Owners", "selection_rule": "Complements omega_H"},
        {"symbol": "Y_H0", "value": p.income_h_0, "unit": "date-0 goods", "interpretation": "Initial aggregate income of H", "selection_rule": "Round synthetic benchmark"},
        {"symbol": "Y_S0", "value": p.income_s_0, "unit": "date-0 goods", "interpretation": "Initial aggregate income of S", "selection_rule": "Round synthetic benchmark"},
        {"symbol": "A_H0", "value": p.assets_h_0, "unit": "date-0 goods", "interpretation": "Initial liquid assets of H", "selection_rule": "Concentrated ownership illustration"},
        {"symbol": "A_S0", "value": p.assets_s_0, "unit": "date-0 goods", "interpretation": "Initial liquid assets of S", "selection_rule": "Concentrated ownership illustration"},
        {"symbol": "m_H=m_T", "value": p.m_h, "unit": "goods per income unit", "interpretation": "Local spending response of H and transfer recipients", "selection_rule": "High-MPC group"},
        {"symbol": "m_S", "value": p.m_s, "unit": "goods per income unit", "interpretation": "Local spending response of owners", "selection_rule": "Low-MPC group"},
        {"symbol": "Z", "value": p.z, "unit": "date-0 goods", "interpretation": "Conditional liquid-income displacement", "selection_rule": "20 percent of initial aggregate income"},
        {"symbol": "P_0=P_1", "value": p.p_0, "unit": "price index", "interpretation": "Normalized prices", "selection_rule": "Numeraire; no inflation claim"},
        {"symbol": "R_B", "value": p.reserve_return, "unit": "gross nominal return", "interpretation": "Treasury deposit return", "selection_rule": "Value-preserving benchmark"},
        {"symbol": "q_0", "value": p.q_0, "unit": "capacity index [0,1]", "interpretation": "Initial institutional capacity", "selection_rule": "Low inherited capacity"},
        {"symbol": "delta_q", "value": p.delta_q, "unit": "rate", "interpretation": "Capacity depreciation", "selection_rule": "Synthetic round value"},
        {"symbol": "d_q", "value": p.damage_q, "unit": "capacity index", "interpretation": "Capacity damage", "selection_rule": "Positive but small"},
        {"symbol": "phi_H", "value": p.phi_high, "unit": "capacity per investment good", "interpretation": "High conversion capacity", "selection_rule": "Makes the declared opportunity floor financeable"},
        {"symbol": "phi_L", "value": p.phi_low, "unit": "capacity per investment good", "interpretation": "Low conversion capacity", "selection_rule": "Same fiscal uses fail the capacity requirement"},
        {"symbol": "a", "value": p.a_operation, "unit": "service per operating good", "interpretation": "Operating-input productivity", "selection_rule": "Unit normalization"},
        {"symbol": "b", "value": p.b_capacity, "unit": "service per capacity unit", "interpretation": "Capacity service ceiling", "selection_rule": "Maximum service equals five"},
        {"symbol": "rho_O", "value": p.rho_o, "unit": "opportunity per service", "interpretation": "Opportunity conversion", "selection_rule": "Unit normalization"},
        {"symbol": "O_0", "value": p.opportunity_0, "unit": "opportunity index", "interpretation": "Initial opportunity", "selection_rule": "Below the target"},
        {"symbol": "O_min", "value": p.opportunity_min, "unit": "opportunity index", "interpretation": "Declared opportunity floor", "selection_rule": "Requires four service units"},
    ]


def scenario_rows(p: Parameters, policies: list[Policy], results: list) -> list[dict]:
    rows = []
    for policy, result in zip(policies, results):
        rows.append({
            "scenario": policy.name,
            "description": policy.description,
            "tax_rate_tau": policy.fiscal.tax_rate,
            "legal_coverage_lambda": policy.fiscal.legal_coverage,
            "compliance_chi": policy.fiscal.compliance,
            "kappa_gross": policy.kappa_gross,
            "T": result.tax,
            "C_adm": policy.admin_cost,
            "R": result.net_public_resources,
            "y_T": policy.transfer_h,
            "I_q": policy.investment_q,
            "B_0": policy.reserve_b0,
            "X_1": policy.operation_x1,
            "phi": policy.phi,
            "delta_D0_dir": result.delta_demand_0,
            "q_1": result.q_1,
            "service_1": result.service_1,
            "O_1": result.opportunity_1,
            "demand_gate": result.demand_gate,
            "opportunity_gate": result.opportunity_gate,
        })
    return rows


def check_rows(p: Parameters, policies: list[Policy], results: list) -> list[dict]:
    rows = []
    for policy, result in zip(policies, results):
        rows.extend(ledger_checks(p, policy, build_ledger(p, policy)))
        for key, value in result.to_dict().items():
            if "residual" in key and not key.startswith("ledger_"):
                rows.append({
                    "scenario": policy.name,
                    "check": key,
                    "check_type": "model_identity",
                    "residual": value,
                    "tolerance": 1.0e-8,
                    "status": "PASS" if abs(value) <= 1.0e-8 else "FAIL",
                    "evidence": "Model-level identity cross-checked after ledger construction",
                })
        domain_checks = {
            "kappa_in_unit_interval": 0 <= policy.kappa_gross <= 1,
            "admin_not_above_tax": policy.admin_cost <= result.tax + 1.0e-10,
            "capacity_in_unit_interval": 0 <= result.q_1 <= 1,
            "operation_within_reserve": policy.operation_x1 <= p.reserve_return * policy.reserve_b0 + 1.0e-10,
            "consumption_nonnegative": min(result.consumption_h, result.consumption_s) >= -1.0e-10,
        }
        for check, passed in domain_checks.items():
            rows.append({
                "scenario": policy.name,
                "check": check,
                "check_type": "domain",
                "residual": 0.0 if passed else 1.0,
                "tolerance": 0.0,
                "status": "PASS" if passed else "FAIL",
                "evidence": "Declared parameter or outcome domain",
            })
    return rows


def analytical_rows(p: Parameters, settings: dict) -> list[dict]:
    rows = []
    phi_cases = {
        "high": p.phi_high,
        "low": p.phi_low,
    }
    for label in settings["analytical"]["capacity_cases"]:
        phi = phi_cases[label]
        req = opportunity_requirement(p, phi)
        for transfer in settings["analytical"]["fixed_transfers"]:
            minimum_finance = transfer + req.investment_min + req.reserve_min
            rows.append({
                "capacity_case": label,
                "phi": phi,
                "target_case": req.status,
                "s_required": req.service_required,
                "X_min": req.operation_min,
                "q_required": req.capacity_min,
                "I_min": req.investment_min,
                "B_min": req.reserve_min,
                "fixed_transfer": transfer,
                "minimum_date0_finance": minimum_finance,
                "available_net_resources": settings["analytical"]["available_net_resources"],
                "fiscally_feasible": minimum_finance <= settings["analytical"]["available_net_resources"] + 1.0e-10,
            })
    return rows


def constructive_case(p: Parameters, policy_c: Policy, settings: dict):
    """Hold Scenario C policy fixed and change only the declared environment."""
    thresholds = fixed_allocation_gate_thresholds(p, policy_c)
    environment = settings["constructive_environment"]
    p_e = replace(p, m_h=float(environment["m_h"]))
    policy_e = replace(
        policy_c,
        name=environment["name"],
        description=environment["description"],
    )
    result_e = compute_scenario(p_e, policy_e)
    row = scenario_rows(p_e, [policy_e], [result_e])[0]
    row.update({
        "m_H": p_e.m_h,
        "m_S": p_e.m_s,
        "demand_m_H_max": thresholds.demand_m_h_max,
        "opportunity_phi_min": thresholds.opportunity_phi_min,
        "comparison_contract": "C fiscal allocation fixed; only m_H differs from C",
    })
    return p_e, policy_e, result_e, thresholds, row


def conditional_region_rows(
    p: Parameters, policy_c: Policy, thresholds, settings: dict
) -> list[dict]:
    """Enumerate the four fixed-policy gate regions for machine checking."""
    rows = []
    region_grid = settings["conditional_region_grid"]
    for m_h in linspace(region_grid["m_h_start"], region_grid["m_h_stop"], region_grid["m_h_count"]):
        for phi in linspace(region_grid["phi_start"], region_grid["phi_stop"], region_grid["phi_count"]):
            delta_demand = thresholds.demand_constant - (
                thresholds.displaced_net_of_transfer * m_h
            )
            q_raw = p.q_preinvestment + phi * policy_c.investment_q
            q_1 = min(1.0, max(0.0, q_raw))
            service_1 = min(
                p.a_operation * policy_c.operation_x1,
                p.b_capacity * q_1,
            )
            opportunity_1 = p.opportunity_0 + p.rho_o * service_1
            demand_gate = delta_demand >= -1.0e-10
            opportunity_gate = opportunity_1 >= p.opportunity_min - 1.0e-10
            region_label = {
                (True, True): "both_pass",
                (True, False): "demand_only",
                (False, True): "opportunity_only",
                (False, False): "neither",
            }[(demand_gate, opportunity_gate)]
            rows.append({
                "m_H": m_h,
                "m_S_fixed": p.m_s,
                "phi": phi,
                "delta_D0_dir": delta_demand,
                "q_1": q_1,
                "O_1": opportunity_1,
                "demand_gate": demand_gate,
                "opportunity_gate": opportunity_gate,
                "region": region_label,
                "policy_allocation": "Scenario C fixed",
            })
    return rows


def sensitivity_rows(p: Parameters, settings: dict) -> list[dict]:
    rows: list[dict] = []
    sweeps = settings["sweeps"]

    def srow(**values) -> dict:
        row = {
            "sweep": "", "parameter_1": "", "value_1": None, "unit_1": "",
            "parameter_2": "", "value_2": None, "unit_2": "",
            "tax_rate_tau": None, "legal_coverage_lambda": None,
            "compliance_chi": None, "kappa_gross": None,
            "fixed_transfer": None, "net_public_resources": None,
            "delta_demand_0": None, "opportunity_index_1": None,
            "minimum_resource_cost": None, "technically_attainable": None,
            "fiscally_feasible": None, "demand_gate": None,
            "opportunity_gate": None, "joint_gate_pass": None,
        }
        row.update(values)
        return row

    for admin_share in sweeps["collection"]["admin_shares"]:
        grid = sweeps["collection"]["tax_rate"]
        for tax_rate in linspace(grid["start"], grid["stop"], grid["count"]):
            fiscal = FiscalInstrument(
                float(tax_rate),
                sweeps["collection"]["legal_coverage"],
                sweeps["collection"]["compliance"],
            )
            tax = fiscal.receipts(p.z)
            admin = admin_share * tax
            transfer = tax - admin
            policy = Policy("sweep", "collection", fiscal, admin, transfer,
                            0.0, 0.0, 0.0, 0.0, 0.0, p.phi_high)
            result = compute_scenario(p, policy)
            rows.append(srow(
                sweep="collection", parameter_1="tax_rate_tau", value_1=tax_rate,
                unit_1="share of legally covered compliant base",
                parameter_2="admin_share_of_T", value_2=admin_share,
                unit_2="share of gross receipts", tax_rate_tau=tax_rate,
                legal_coverage_lambda=fiscal.legal_coverage,
                compliance_chi=fiscal.compliance,
                kappa_gross=fiscal.kappa_gross, fixed_transfer=transfer,
                net_public_resources=tax - admin,
                delta_demand_0=result.delta_demand_0, demand_gate=result.demand_gate,
            ))

    grid = sweeps["administration"]
    for admin in linspace(grid["start"], grid["stop"], grid["count"]):
        transfer = p.z - admin
        fiscal = FiscalInstrument(
            grid["tax_rate"], grid["legal_coverage"], grid["compliance"]
        )
        policy = Policy("sweep", "administration", fiscal, admin, transfer,
                        0.0, 0.0, 0.0, 0.0, 0.0, p.phi_high)
        result = compute_scenario(p, policy)
        rows.append(srow(
            sweep="administration", parameter_1="C_adm", value_1=admin,
            unit_1="date-0 goods", parameter_2="tax_rate_tau", value_2=fiscal.tax_rate,
            unit_2="share", tax_rate_tau=fiscal.tax_rate,
            legal_coverage_lambda=fiscal.legal_coverage,
            compliance_chi=fiscal.compliance, kappa_gross=fiscal.kappa_gross,
            fixed_transfer=transfer,
            net_public_resources=transfer, delta_demand_0=result.delta_demand_0,
            demand_gate=result.demand_gate,
        ))

    joint_grid = sweeps["mpc_joint_gate"]
    for m_h in linspace(joint_grid["m_h_start"], joint_grid["m_h_stop"], joint_grid["m_h_count"]):
        for m_s in linspace(joint_grid["m_s_start"], joint_grid["m_s_stop"], joint_grid["m_s_count"]):
            if m_s >= m_h:
                continue
            pp = replace(p, m_h=float(m_h), m_s=float(m_s))
            joint = maximum_joint_demand(
                pp,
                joint_grid["tax_rate"],
                joint_grid["admin_cost"],
                pp.phi_high,
                joint_grid["legal_coverage"],
                joint_grid["compliance"],
            )
            feasible = bool(joint.get("feasible", False))
            demand_pass = bool(joint.get("demand_gate", False)) if feasible else None
            rows.append(srow(
                sweep="mpc_joint_gate", parameter_1="m_H", value_1=m_h,
                unit_1="goods per income unit", parameter_2="m_S", value_2=m_s,
                unit_2="goods per income unit", tax_rate_tau=joint_grid["tax_rate"],
                legal_coverage_lambda=joint_grid["legal_coverage"],
                compliance_chi=joint_grid["compliance"],
                kappa_gross=(joint_grid["tax_rate"] * joint_grid["legal_coverage"] * joint_grid["compliance"]),
                net_public_resources=p.z * joint_grid["tax_rate"] * joint_grid["legal_coverage"] * joint_grid["compliance"] - joint_grid["admin_cost"],
                delta_demand_0=joint.get("delta_demand_max") if feasible else None,
                minimum_resource_cost=joint.get("minimum_total"),
                technically_attainable=True, fiscally_feasible=feasible,
                demand_gate=demand_pass, joint_gate_pass=demand_pass,
            ))

    capacity_grid = sweeps["capacity"]
    for phi in linspace(capacity_grid["start"], capacity_grid["stop"], capacity_grid["count"]):
        allocation = settings["fixed_allocation"]
        fiscal = FiscalInstrument(**allocation["fiscal"])
        policy = Policy(
            "sweep", "capacity", fiscal, allocation["admin_cost"],
            allocation["transfer_h"], allocation["investment_q"],
            allocation["reserve_b0"], allocation["operation_x1"],
            allocation["reserve_b1"], allocation["unused_u0"], float(phi),
        )
        result = compute_scenario(p, policy)
        rows.append(srow(
            sweep="capacity", parameter_1="phi", value_1=phi,
            unit_1="capacity per investment good", parameter_2="I_q",
            value_2=allocation["investment_q"],
            unit_2="date-0 goods", tax_rate_tau=fiscal.tax_rate,
            legal_coverage_lambda=fiscal.legal_coverage,
            compliance_chi=fiscal.compliance, kappa_gross=fiscal.kappa_gross,
            fixed_transfer=allocation["transfer_h"],
            net_public_resources=policy.tax(p) - allocation["admin_cost"],
            delta_demand_0=result.delta_demand_0,
            opportunity_index_1=result.opportunity_1,
            technically_attainable=True, fiscally_feasible=True,
            demand_gate=result.demand_gate, opportunity_gate=result.opportunity_gate,
            joint_gate_pass=result.demand_gate and result.opportunity_gate,
        ))

    depreciation_grid = sweeps["depreciation"]
    for delta in linspace(depreciation_grid["start"], depreciation_grid["stop"], depreciation_grid["count"]):
        pp = replace(p, delta_q=float(delta))
        allocation = settings["fixed_allocation"]
        fiscal = FiscalInstrument(**allocation["fiscal"])
        policy = Policy(
            "sweep", "depreciation", fiscal, allocation["admin_cost"],
            allocation["transfer_h"], allocation["investment_q"],
            allocation["reserve_b0"], allocation["operation_x1"],
            allocation["reserve_b1"], allocation["unused_u0"], pp.phi_high,
        )
        result = compute_scenario(pp, policy)
        rows.append(srow(
            sweep="depreciation", parameter_1="delta_q", value_1=delta,
            unit_1="rate", parameter_2="phi", value_2=pp.phi_high,
            unit_2="capacity per investment good", tax_rate_tau=fiscal.tax_rate,
            legal_coverage_lambda=fiscal.legal_coverage,
            compliance_chi=fiscal.compliance, kappa_gross=fiscal.kappa_gross,
            fixed_transfer=allocation["transfer_h"],
            net_public_resources=policy.tax(pp) - allocation["admin_cost"],
            delta_demand_0=result.delta_demand_0,
            opportunity_index_1=result.opportunity_1,
            technically_attainable=True, fiscally_feasible=True,
            demand_gate=result.demand_gate, opportunity_gate=result.opportunity_gate,
            joint_gate_pass=result.demand_gate and result.opportunity_gate,
        ))

    target_grid = sweeps["opportunity_target"]
    target_start = p.opportunity_0 + target_grid["start_offset"]
    target_stop = p.opportunity_0 + p.rho_o * p.b_capacity + target_grid["stop_offset_from_ceiling"]
    for target in linspace(target_start, target_stop, target_grid["count"]):
        pp = replace(p, opportunity_min=float(target))
        for label, phi in (("phi_high", p.phi_high), ("phi_low", p.phi_low)):
            req = opportunity_requirement(pp, phi)
            total = req.investment_min + req.reserve_min
            technical = req.status != "technically_impossible"
            fixed_transfer = settings["fixed_allocation"]["transfer_h"]
            available = settings["analytical"]["available_net_resources"]
            fiscal = technical and fixed_transfer + total <= available + 1.0e-10
            rows.append(srow(
                sweep="opportunity_target", parameter_1="O_min", value_1=target,
                unit_1="opportunity index", parameter_2=label, value_2=phi,
                unit_2="capacity per investment good", tax_rate_tau=settings["fixed_allocation"]["fiscal"]["tax_rate"],
                legal_coverage_lambda=settings["fixed_allocation"]["fiscal"]["legal_coverage"],
                compliance_chi=settings["fixed_allocation"]["fiscal"]["compliance"],
                kappa_gross=(settings["fixed_allocation"]["fiscal"]["tax_rate"] * settings["fixed_allocation"]["fiscal"]["legal_coverage"] * settings["fixed_allocation"]["fiscal"]["compliance"]),
                fixed_transfer=fixed_transfer, net_public_resources=available,
                minimum_resource_cost=total if technical else None,
                technically_attainable=technical, fiscally_feasible=fiscal,
            ))
    return rows


INK = colors.HexColor("#252A34")
GRID = colors.HexColor("#D9DEE7")
BLUE = colors.HexColor("#2F5597")
ORANGE = colors.HexColor("#C55A11")
OLIVE = colors.HexColor("#6B7A2A")
LIGHT = colors.HexColor("#F4F6F9")


def add_axes(
    drawing: Drawing,
    x0: float,
    y0: float,
    width: float,
    height: float,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    xticks: list[float],
    yticks: list[float],
    xlabel: str,
    ylabel: str,
    title: str,
):
    def sx(value: float) -> float:
        return x0 + width * (value - xmin) / (xmax - xmin)

    def sy(value: float) -> float:
        return y0 + height * (value - ymin) / (ymax - ymin)

    drawing.add(Rect(x0, y0, width, height, fillColor=colors.white, strokeColor=GRID, strokeWidth=0.7))
    for value in yticks:
        yy = sy(value)
        drawing.add(Line(x0, yy, x0 + width, yy, strokeColor=GRID, strokeWidth=0.45))
        drawing.add(String(x0 - 5, yy - 3, f"{value:g}", fontName="Helvetica", fontSize=7, fillColor=INK, textAnchor="end"))
    for value in xticks:
        xx = sx(value)
        drawing.add(Line(xx, y0, xx, y0 - 3, strokeColor=INK, strokeWidth=0.55))
        drawing.add(String(xx, y0 - 13, f"{value:g}", fontName="Helvetica", fontSize=7, fillColor=INK, textAnchor="middle"))
    drawing.add(Line(x0, y0, x0 + width, y0, strokeColor=INK, strokeWidth=0.8))
    drawing.add(Line(x0, y0, x0, y0 + height, strokeColor=INK, strokeWidth=0.8))
    drawing.add(String(x0 + width / 2, y0 - 27, xlabel, fontName="Helvetica", fontSize=8, fillColor=INK, textAnchor="middle"))
    drawing.add(Rect(x0 + 2, y0 + height - 16, 105, 13, fillColor=colors.white, strokeColor=None))
    drawing.add(String(x0 + 5, y0 + height - 13, ylabel, fontName="Helvetica", fontSize=7.5, fillColor=INK))
    drawing.add(String(x0, y0 + height + 13, title, fontName="Helvetica-Bold", fontSize=9, fillColor=INK))
    return sx, sy


def save_drawing(drawing: Drawing, stem: str) -> None:
    renderPDF.drawToFile(drawing, str(FIGURES / f"{stem}.pdf"))
    renderSVG.drawToFile(drawing, str(FIGURES / f"{stem}.svg"))


def diverging_color(value: float, scale: float):
    ratio = min(1.0, abs(value) / max(scale, 1.0e-12))
    endpoint = BLUE if value < 0 else ORANGE
    return colors.Color(
        1.0 + ratio * (endpoint.red - 1.0),
        1.0 + ratio * (endpoint.green - 1.0),
        1.0 + ratio * (endpoint.blue - 1.0),
    )


def create_figures(
    p: Parameters,
    scenarios: list[dict],
    sensitivity: list[dict],
    constructive: dict,
    thresholds,
) -> None:
    # Chart contract 1: collection and MPC heterogeneity determine whether the
    # direct-demand gate can be reached.  Line plus heatmap; static PDF/SVG.
    drawing = Drawing(720, 300)
    sx, sy = add_axes(
        drawing, 55, 48, 270, 205, 0, 1, -13, 2,
        [0, 0.25, 0.5, 0.75, 1], [-12, -9, -6, -3, 0],
        "Tax rate tau (lambda=chi=1)", "Direct demand change", "Transfer policy and fiscal capture",
    )
    styles = ((0.0, BLUE, None), (0.05, ORANGE, [5, 3]), (0.10, OLIVE, [2, 2]))
    for share, color, dash in styles:
        subset = [r for r in sensitivity if r["sweep"] == "collection" and abs(r["value_2"] - share) < 1.0e-12]
        points = []
        for row in subset:
            points.extend((sx(row["value_1"]), sy(row["delta_demand_0"])))
        line = PolyLine(points, strokeColor=color, strokeWidth=1.5, fillColor=None)
        if dash:
            line.strokeDashArray = dash
        drawing.add(line)
    drawing.add(Line(55, sy(0), 325, sy(0), strokeColor=INK, strokeWidth=0.9))
    for idx, (share, color, dash) in enumerate(styles):
        yy = 278 - idx * 12
        line = Line(190, yy, 211, yy, strokeColor=color, strokeWidth=1.5)
        if dash:
            line.strokeDashArray = dash
        drawing.add(line)
        drawing.add(String(215, yy - 3, f"C_adm/T = {share:.0%}", fontName="Helvetica", fontSize=7, fillColor=INK))

    x0, y0, width, height = 410, 48, 270, 205
    mh_grid = linspace(0.40, 0.95, 56)
    ms_grid = linspace(0.10, 0.50, 41)
    lookup = {(round(r["value_1"], 8), round(r["value_2"], 8)): r["delta_demand_0"] for r in sensitivity if r["sweep"] == "mpc_joint_gate"}
    valid = [float(v) for v in lookup.values() if v is not None and math.isfinite(float(v))]
    scale = max(abs(min(valid)), abs(max(valid)))
    cell_w, cell_h = width / len(mh_grid), height / len(ms_grid)
    drawing.add(String(x0, y0 + height + 13, "Best direct demand with opportunity floor", fontName="Helvetica-Bold", fontSize=9, fillColor=INK))
    drawing.add(String(x0, y0 + height + 3, "Full capture: the m_S term cancels", fontName="Helvetica", fontSize=7, fillColor=INK))
    boundary = []
    for i, ms in enumerate(ms_grid):
        row_values = []
        for j, mh in enumerate(mh_grid):
            value = lookup.get((round(mh, 8), round(ms, 8)))
            fill = LIGHT if value is None else diverging_color(float(value), scale)
            drawing.add(Rect(x0 + j * cell_w, y0 + i * cell_h, cell_w + 0.2, cell_h + 0.2, fillColor=fill, strokeColor=None))
            if value is not None:
                row_values.append((mh, float(value)))
        if row_values:
            mh_star = min(row_values, key=lambda item: abs(item[1]))[0]
            boundary.extend((x0 + width * (mh_star - 0.40) / 0.55, y0 + height * (ms - 0.10) / 0.40))
    drawing.add(Rect(x0, y0, width, height, fillColor=None, strokeColor=INK, strokeWidth=0.8))
    if len(boundary) >= 4:
        drawing.add(PolyLine(boundary, strokeColor=INK, strokeWidth=1.0, fillColor=None))
    bx = x0 + width * (p.m_h - 0.40) / 0.55
    by = y0 + height * (p.m_s - 0.10) / 0.40
    drawing.add(Circle(bx, by, 3.2, fillColor=INK, strokeColor=colors.white, strokeWidth=0.7))
    for value in [0.4, 0.55, 0.7, 0.85, 0.95]:
        xx = x0 + width * (value - 0.40) / 0.55
        drawing.add(String(xx, y0 - 13, f"{value:.2g}", fontName="Helvetica", fontSize=7, fillColor=INK, textAnchor="middle"))
    for value in [0.1, 0.2, 0.3, 0.4, 0.5]:
        yy = y0 + height * (value - 0.10) / 0.40
        drawing.add(String(x0 - 5, yy - 3, f"{value:.1f}", fontName="Helvetica", fontSize=7, fillColor=INK, textAnchor="end"))
    drawing.add(String(x0 + width / 2, y0 - 27, "m_H", fontName="Helvetica", fontSize=8, fillColor=INK, textAnchor="middle"))
    drawing.add(Rect(x0 + 2, y0 + height - 16, 28, 13, fillColor=colors.white, strokeColor=None))
    drawing.add(String(x0 + 5, y0 + height - 13, "m_S", fontName="Helvetica", fontSize=7.5, fillColor=INK))
    drawing.add(String(x0 + 5, y0 + 5, "blue: shortfall", fontName="Helvetica", fontSize=7, fillColor=INK))
    drawing.add(String(x0 + width - 5, y0 + 5, "orange: passage", fontName="Helvetica", fontSize=7, fillColor=INK, textAnchor="end"))
    drawing.add(String(bx + 5, by + 4, "benchmark", fontName="Helvetica", fontSize=7, fillColor=INK))
    save_drawing(drawing, "demand_sensitivity")

    # Chart contract 2: the same fiscal uses cross the opportunity floor only
    # with sufficient conversion capacity; line comparisons and benchmarks.
    drawing = Drawing(720, 300)
    sx, sy = add_axes(
        drawing, 55, 48, 270, 205, 0.04, 0.35, 0.5, 6.2,
        [0.05, 0.10, 0.20, 0.30, 0.35], [1, 2, 3, 4, 5, 6],
        "Conversion efficiency phi", "Opportunity O_1", "Same fiscal uses, different capacity",
    )
    capacity = [r for r in sensitivity if r["sweep"] == "capacity"]
    points = []
    for row in capacity:
        points.extend((sx(row["value_1"]), sy(row["opportunity_index_1"])))
    drawing.add(PolyLine(points, strokeColor=BLUE, strokeWidth=1.7, fillColor=None))
    floor = Line(55, sy(p.opportunity_min), 325, sy(p.opportunity_min), strokeColor=INK, strokeWidth=0.9)
    floor.strokeDashArray = [5, 3]
    drawing.add(floor)
    for phi, color, label in ((p.phi_low, ORANGE, "low phi"), (p.phi_high, OLIVE, "high phi")):
        xx = sx(phi)
        marker = Line(xx, 48, xx, 253, strokeColor=color, strokeWidth=1.0)
        marker.strokeDashArray = [2, 2]
        drawing.add(marker)
        drawing.add(String(xx + 4, 218, label, fontName="Helvetica", fontSize=7, fillColor=color))

    sx2, sy2 = add_axes(
        drawing, 410, 48, 270, 205, 1.0, 6.5, 0, 18,
        [1, 2, 3, 4, 5, 6], [0, 3, 6, 9, 12, 15, 18],
        "Opportunity floor O_min", "Minimum I_q + B_0", "Resources required by the opportunity gate",
    )
    for label, color, dash in (("phi_high", OLIVE, None), ("phi_low", ORANGE, [5, 3])):
        subset = [
            r for r in sensitivity
            if r["sweep"] == "opportunity_target" and r["parameter_2"] == label
            and r["technically_attainable"] and r["minimum_resource_cost"] is not None
        ]
        points = []
        for row in subset:
            points.extend((sx2(row["value_1"]), sy2(row["minimum_resource_cost"])))
        line = PolyLine(points, strokeColor=color, strokeWidth=1.6, fillColor=None)
        if dash:
            line.strokeDashArray = dash
        drawing.add(line)
    available = Line(410, sy2(7.0), 680, sy2(7.0), strokeColor=INK, strokeWidth=0.9)
    available.strokeDashArray = [5, 3]
    drawing.add(available)
    ceiling_x = sx2(p.opportunity_0 + p.rho_o * p.b_capacity)
    ceiling = Line(ceiling_x, 48, ceiling_x, 253, strokeColor=colors.gray, strokeWidth=0.9)
    ceiling.strokeDashArray = [2, 2]
    drawing.add(ceiling)
    drawing.add(String(415, sy2(7.0) + 4, "available after y_T=12", fontName="Helvetica", fontSize=7, fillColor=INK))
    drawing.add(Line(610, 278, 624, 278, strokeColor=OLIVE, strokeWidth=1.6))
    drawing.add(String(629, 275, "high phi", fontName="Helvetica", fontSize=7, fillColor=OLIVE))
    low_key = Line(610, 266, 624, 266, strokeColor=ORANGE, strokeWidth=1.6)
    low_key.strokeDashArray = [5, 3]
    drawing.add(low_key)
    drawing.add(String(629, 263, "low phi", fontName="Helvetica", fontSize=7, fillColor=ORANGE))
    drawing.add(String(ceiling_x - 3, 58, "technical ceiling", fontName="Helvetica", fontSize=7, fillColor=colors.gray, angle=90))
    save_drawing(drawing, "opportunity_sensitivity")

    # Chart contract 3: four named policy scenarios in the two-gate plane.
    drawing = Drawing(500, 360)
    sx, sy = add_axes(
        drawing, 75, 58, 365, 235, -13, 1, -5, 1,
        [-12, -9, -6, -3, 0], [-4, -3, -2, -1, 0, 1],
        "Direct demand gate margin", "Opportunity gate margin", "Four scenarios in the two-gate plane",
    )
    drawing.add(Line(sx(0), 58, sx(0), 293, strokeColor=INK, strokeWidth=1.0))
    drawing.add(Line(75, sy(0), 440, sy(0), strokeColor=INK, strokeWidth=1.0))
    for row in scenarios:
        xx, yy = sx(row["delta_D0_dir"]), sy(row["O_1"] - p.opportunity_min)
        fill = ORANGE if row["demand_gate"] else BLUE
        drawing.add(Circle(xx, yy, 5, fillColor=fill, strokeColor=INK, strokeWidth=0.7))
        drawing.add(String(xx + 7, yy + 4, row["scenario"], fontName="Helvetica-Bold", fontSize=9, fillColor=INK))
    drawing.add(String(78, 321, "x=0: demand passage; y=0: opportunity passage", fontName="Helvetica", fontSize=8, fillColor=INK))
    save_drawing(drawing, "scenario_gate_map")

    # Chart contract 4: fixed Scenario C allocation, with m_H and phi varying.
    drawing = Drawing(620, 410)
    x0, y0, width, height = 82, 60, 470, 285
    x_min, x_max = 0.31, 0.95
    y_min, y_max = 0.04, 0.35
    sx, sy = add_axes(
        drawing, x0, y0, width, height, x_min, x_max, y_min, y_max,
        [0.35, 0.50, 0.65, 0.80, 0.95], [0.05, 0.10, 0.20, 0.25, 0.30, 0.35],
        "Exposed-group spending response m_H", "Conversion efficiency phi",
        "Conditional gate regions under the fixed Scenario C allocation",
    )
    x_star = sx(thresholds.demand_m_h_max)
    y_star = sy(thresholds.opportunity_phi_min)
    pale_blue = colors.Color(0.88, 0.93, 0.98)
    pale_orange = colors.Color(0.98, 0.91, 0.84)
    pale_green = colors.Color(0.90, 0.95, 0.84)
    pale_gray = colors.Color(0.94, 0.94, 0.94)
    drawing.add(Rect(x0, y0, x_star - x0, y_star - y0,
                     fillColor=pale_blue, strokeColor=None))
    drawing.add(Rect(x0, y_star, x_star - x0, y0 + height - y_star,
                     fillColor=pale_green, strokeColor=None))
    drawing.add(Rect(x_star, y0, x0 + width - x_star, y_star - y0,
                     fillColor=pale_gray, strokeColor=None))
    drawing.add(Rect(x_star, y_star, x0 + width - x_star, y0 + height - y_star,
                     fillColor=pale_orange, strokeColor=None))
    drawing.add(Rect(x0, y0, width, height, fillColor=None, strokeColor=INK, strokeWidth=0.8))
    vertical = Line(x_star, y0, x_star, y0 + height, strokeColor=INK, strokeWidth=1.1)
    vertical.strokeDashArray = [5, 3]
    drawing.add(vertical)
    horizontal = Line(x0, y_star, x0 + width, y_star, strokeColor=INK, strokeWidth=1.1)
    horizontal.strokeDashArray = [5, 3]
    drawing.add(horizontal)
    drawing.add(String((x0 + x_star) / 2, (y0 + y_star) / 2,
                       "Demand only", fontName="Helvetica-Bold", fontSize=9,
                       fillColor=INK, textAnchor="middle"))
    drawing.add(String((x0 + x_star) / 2, (y_star + y0 + height) / 2,
                       "Both pass", fontName="Helvetica-Bold", fontSize=9,
                       fillColor=INK, textAnchor="middle"))
    drawing.add(String((x_star + x0 + width) / 2, (y0 + y_star) / 2,
                       "Neither", fontName="Helvetica-Bold", fontSize=9,
                       fillColor=INK, textAnchor="middle"))
    drawing.add(String((x_star + x0 + width) / 2, (y_star + y0 + height) / 2,
                       "Opportunity only", fontName="Helvetica-Bold", fontSize=9,
                       fillColor=INK, textAnchor="middle"))
    drawing.add(String(x_star + 5, y0 + 7, "m_H*=0.500", fontName="Helvetica", fontSize=8,
                       fillColor=INK))
    drawing.add(String(x0 + 5, y_star + 5, "phi*=0.2433", fontName="Helvetica", fontSize=8,
                       fillColor=INK))
    markers = (
        (p.m_h, p.phi_high, "C", BLUE),
        (p.m_h, p.phi_low, "D", BLUE),
        (constructive["m_H"], constructive["phi"], "E", ORANGE),
    )
    for m_h, phi, label, color in markers:
        xx, yy = sx(m_h), sy(phi)
        drawing.add(Circle(xx, yy, 5.2, fillColor=color, strokeColor=INK, strokeWidth=0.7))
        drawing.add(String(xx + 8, yy + 4, label, fontName="Helvetica-Bold", fontSize=9,
                           fillColor=INK))
    save_drawing(drawing, "conditional_gate_regions")


def latex_tables(
    params: list[dict], scenarios: list[dict], checks: list[dict],
    analytical: list[dict], constructive: dict
) -> None:
    selected = [r for r in params if r["symbol"] in {"omega_H", "omega_S", "m_H=m_T", "m_S", "Z", "R_B", "q_0", "delta_q", "d_q", "phi_H", "phi_L", "a", "b", "rho_O", "O_0", "O_min"}]
    lines = [r"\begin{tabularx}{\textwidth}{l r l X}", r"\toprule", r"Symbol & Value & Unit & Interpretation \\", r"\midrule"]
    symbol_map = {
        "omega_H": r"$\omega_H$", "omega_S": r"$\omega_S$", "m_H=m_T": r"$m_H=m_T$", "m_S": r"$m_S$", "Z": r"$Z$", "R_B": r"$R_B$", "q_0": r"$q_0$", "delta_q": r"$\delta_q$", "d_q": r"$d_q$", "phi_H": r"$\phi_H$", "phi_L": r"$\phi_L$", "a": r"$a$", "b": r"$b$", "rho_O": r"$\rho_O$", "O_0": r"$O_0$", "O_min": r"$O_{\min}$",
    }
    for row in selected:
        unit = row["unit"].replace("%", r"\%").replace("_", r"\_")
        text = row["interpretation"].replace("_", r"\_")
        lines.append(f"{symbol_map[row['symbol']]} & {fmt(float(row['value']))} & {unit} & {text} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabularx}"])
    (RESULTS / "parameters_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    lines = [r"\begin{tabular}{lrrrrrrrr}", r"\toprule", r"Scenario & $T$ & $y_T$ & $I_q$ & $B_0$ & $\Delta D_0^{dir}$ & $q_1$ & $O_1$ & Gates \\", r"\midrule"]
    for row in scenarios:
        gates = ("D" if row["demand_gate"] else "--") + "/" + ("O" if row["opportunity_gate"] else "--")
        lines.append(f"{row['scenario']} & {fmt(row['T'])} & {fmt(row['y_T'])} & {fmt(row['I_q'])} & {fmt(row['B_0'])} & {fmt(row['delta_D0_dir'])} & {fmt(row['q_1'])} & {fmt(row['O_1'])} & {gates} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    (RESULTS / "scenarios_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    lines = [r"\begin{tabular}{lrrrrl}", r"\toprule", r"Case & $\phi$ & $X_{\min}$ & $I_{\min}$ & $I_{\min}+B_{\min}+12$ & Feasible \\", r"\midrule"]
    for row in analytical:
        if row["fixed_transfer"] != 12.0:
            continue
        lines.append(f"{row['capacity_case'].title()} & {fmt(row['phi'])} & {fmt(row['X_min'])} & {fmt(row['I_min'])} & {fmt(row['minimum_date0_finance'])} & {'yes' if row['fiscally_feasible'] else 'no'} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    (RESULTS / "analytical_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    residual_checks = [r for r in checks if "residual" in r["check"]]
    lines = [r"\begin{tabular}{lrrl}", r"\toprule", r"Scenario & Maximum absolute residual & Residual checks & Status \\", r"\midrule"]
    for scenario in "ABCD":
        subset = [r for r in residual_checks if r["scenario"] == scenario]
        maximum = max(abs(float(r["residual"])) for r in subset)
        status = "PASS" if all(r["status"] == "PASS" for r in subset) else "FAIL"
        lines.append(f"{scenario} & {maximum:.2e} & {len(subset)} & {status} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    (RESULTS / "accounting_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    comparison = [next(row for row in scenarios if row["scenario"] == "C"), constructive]
    lines = [
        r"\begin{tabular}{llrrrrrl}", r"\toprule",
        r"Environment & Fixed allocation & $m_H$ & $\phi$ & $\Delta D_0^{dir}$ & $q_1$ & $O_1$ & Gates \\",
        r"\midrule",
    ]
    for row in comparison:
        label = "C" if row["scenario"] == "C" else "E"
        allocation = "C" if label == "C" else "C (unchanged)"
        m_h = params[6]["value"] if label == "C" else row["m_H"]
        gates = ("D" if row["demand_gate"] else "--") + "/" + ("O" if row["opportunity_gate"] else "--")
        lines.append(
            f"{label} & {allocation} & {fmt(float(m_h))} & {fmt(row['phi'])} & "
            f"{fmt(row['delta_D0_dir'])} & {fmt(row['q_1'])} & {fmt(row['O_1'])} & {gates} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    (RESULTS / "constructive_case_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def optimization_rows(p: Parameters, settings: dict) -> list[dict]:
    """Compute the two policy-allocation maxima reported by the manuscript.

    The second row removes only the productive-investment ceiling. Frozen
    reference values are not available to this function.
    """
    allocation = settings["fixed_allocation"]
    fiscal = FiscalInstrument(**allocation["fiscal"])
    phi = p.phi_high
    constrained = maximum_joint_demand(
        p,
        fiscal.tax_rate,
        allocation["admin_cost"],
        phi,
        fiscal.legal_coverage,
        fiscal.compliance,
    )
    requirement = opportunity_requirement(p, phi)
    resources = fiscal.receipts(p.z) - allocation["admin_cost"]
    allocatable = resources - requirement.reserve_min
    investment = allocatable if p.d_investment > p.m_h else requirement.investment_min
    transfer = allocatable - investment
    base = (
        -p.m_h * p.z
        + p.m_s * (p.z - fiscal.receipts(p.z))
        + p.d_admin * allocation["admin_cost"]
    )
    unconstrained_value = base + p.m_h * transfer + p.d_investment * investment
    return [
        {
            "case": "productive_investment_ceiling",
            "delta_demand_max": constrained["delta_demand_max"],
            "investment": constrained["investment"],
            "transfer": constrained["transfer"],
            "reserve": constrained["reserve"],
            "opportunity_floor_financed": constrained["feasible"],
            "unit": "date-0 goods at P0=P1=1",
        },
        {
            "case": "no_productive_investment_ceiling",
            "delta_demand_max": unconstrained_value,
            "investment": investment,
            "transfer": transfer,
            "reserve": requirement.reserve_min,
            "opportunity_floor_financed": resources + 1.0e-10 >= requirement.investment_min + requirement.reserve_min,
            "unit": "date-0 goods at P0=P1=1",
        },
    ]


def generate_outputs(
    output_root: Path,
    package_root: Path,
    p: Parameters,
    policies: list[Policy],
    settings: dict,
    run_context: dict,
) -> dict:
    """Recompute and write every P2 result into a fresh staging directory."""
    global RESULTS, FIGURES, PROVENANCE
    RESULTS = output_root / "results"
    FIGURES = output_root / "figures"
    PROVENANCE = package_root / "provenance" / "source_manifest.json"
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    manifest = load_provenance_manifest()
    provenance_check = {"status": "local_manifest_loaded", "root": None, "sources": []}
    results = [compute_scenario(p, policy) for policy in policies]
    policy_by_name = {policy.name: policy for policy in policies}
    base_policy_name = settings["constructive_environment"]["base_policy"]
    p_e, policy_e, result_e, thresholds, constructive = constructive_case(
        p, policy_by_name[base_policy_name], settings
    )

    params = parameter_rows(p)
    scenarios = scenario_rows(p, policies, results)
    checks = check_rows(p, policies, results)
    ledger_entries = [
        entry.to_dict() for policy in policies for entry in build_ledger(p, policy)
    ]
    cash_entries = [row for row in ledger_entries if row["record_type"] == "cash"]
    balance_entries = [row for row in ledger_entries if row["record_type"] == "balance_sheet"]
    analytical = analytical_rows(p, settings)
    sensitivity = sensitivity_rows(p, settings)
    conditional_regions = conditional_region_rows(
        p, policy_by_name[base_policy_name], thresholds, settings
    )
    optimization = optimization_rows(p, settings)
    constructive_checks = check_rows(p_e, [policy_e], [result_e])
    core_failed = [row for row in checks if row["status"] != "PASS"]
    constructive_failed = [
        row for row in constructive_checks if row["status"] != "PASS"
    ]
    failed = core_failed + constructive_failed
    if failed:
        failure_summary = {
            "core_checks": len(checks),
            "core_failed_checks": len(core_failed),
            "constructive_checks": len(constructive_checks),
            "constructive_failed_checks": len(constructive_failed),
            "total_checks": len(checks) + len(constructive_checks),
            "total_failed_checks": len(failed),
            "first_failures": failed[:10],
        }
        raise AssertionError(
            "Accounting or domain checks failed before output publication: "
            + json.dumps(failure_summary, sort_keys=True)
        )
    constructive_ledger = [entry.to_dict() for entry in build_ledger(p_e, policy_e)]

    write_csv(RESULTS / "parameters.csv", params)
    write_csv(RESULTS / "scenarios.csv", scenarios)
    write_csv(RESULTS / "accounting_checks.csv", checks)
    write_csv(RESULTS / "ledger_entries.csv", ledger_entries)
    write_csv(RESULTS / "cash_ledger.csv", cash_entries)
    write_csv(RESULTS / "balance_sheet_ledger.csv", balance_entries)
    write_csv(RESULTS / "analytical_conditions.csv", analytical)
    write_csv(RESULTS / "sensitivity.csv", sensitivity)
    write_csv(RESULTS / "constructive_case.csv", [constructive])
    write_csv(RESULTS / "constructive_case_accounting_checks.csv", constructive_checks)
    write_csv(RESULTS / "constructive_case_ledger_entries.csv", constructive_ledger)
    write_csv(RESULTS / "fixed_policy_gate_thresholds.csv", [asdict(thresholds)])
    write_csv(RESULTS / "conditional_gate_regions.csv", conditional_regions)
    write_csv(RESULTS / "optimization_summary.csv", optimization)
    create_figures(p, scenarios, sensitivity, constructive, thresholds)
    latex_tables(params, scenarios, checks, analytical, constructive)

    metadata = {
        **run_context,
        "python": sys.version,
        "platform": platform.platform(),
        "reportlab": __import__("reportlab").Version,
        "model_scope": "incidence and direct demand; not equilibrium output",
        "price_domain": "P0=P1=R_B=1",
        "provenance_manifest": manifest,
        "external_provenance_check": provenance_check,
        "source_hashes": {
            "model_py": sha256(Path(__file__).with_name("model.py")),
            "generation_py": sha256(Path(__file__)),
            "test_model_py": sha256(package_root / "tests" / "test_model_legacy.py"),
            "test_generator_integration_py": sha256(
                package_root / "tests" / "test_generator_integration_legacy.py"
            ),
        },
    }
    (RESULTS / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    summary = {
        "scenarios": [{"name": r.name, "delta_D": r.delta_demand_0, "O1": r.opportunity_1, "gates": [r.demand_gate, r.opportunity_gate]} for r in results],
        "constructive_case": {"name": result_e.name, "delta_D": result_e.delta_demand_0,
                              "O1": result_e.opportunity_1,
                              "gates": [result_e.demand_gate, result_e.opportunity_gate]},
        "core_checks": len(checks),
        "core_failed_checks": len(core_failed),
        "sensitivity_rows": len(sensitivity),
        "ledger_entries": len(ledger_entries),
        "constructive_checks": len(constructive_checks),
        "constructive_failed_checks": len(constructive_failed),
        "total_checks": len(checks) + len(constructive_checks),
        "total_failed_checks": len(failed),
        "constructive_ledger_entries": len(constructive_ledger),
        "conditional_region_rows": len(conditional_regions),
        "optimization": optimization,
        "provenance_check": provenance_check["status"],
    }
    return summary
