"""Two-date reduced economy for the automation manuscript.

The module computes incidence, direct demand, public accounts, installed
capacity, and an opportunity indicator. Version 4 retains the auditable double-
entry ledger, explicit scalar fiscal instrument, and constructive fixed-policy
gate-region diagnostic. It also closes the fixed-operation and already-met
objective edge cases. It deliberately does
not solve for equilibrium output, prices, or a HANK transition.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List


TOL = 1.0e-10
UNIT = "date-0 goods at P0=P1=1"


@dataclass(frozen=True)
class Parameters:
    omega_h: float = 0.80
    omega_s: float = 0.20
    income_h_0: float = 80.0
    income_s_0: float = 20.0
    consumption_h_0: float = 72.0
    consumption_s_0: float = 8.0
    assets_h_0: float = 10.0
    assets_s_0: float = 90.0
    m_h: float = 0.90
    m_s: float = 0.30
    z: float = 20.0
    p_0: float = 1.0
    p_1: float = 1.0
    d_admin: float = 1.0
    d_investment: float = 1.0
    d_operation: float = 1.0
    reserve_return: float = 1.0
    q_0: float = 0.10
    delta_q: float = 0.10
    damage_q: float = 0.02
    phi_high: float = 0.25
    phi_low: float = 0.08
    a_operation: float = 1.0
    b_capacity: float = 5.0
    rho_o: float = 1.0
    opportunity_0: float = 1.0
    opportunity_min: float = 5.0

    def validate(self) -> None:
        if abs(self.omega_h + self.omega_s - 1.0) > TOL:
            raise ValueError("Population masses must sum to one.")
        if min(self.omega_h, self.omega_s) <= 0:
            raise ValueError("Population masses must be positive.")
        if not (0 <= self.m_s < self.m_h <= 1):
            raise ValueError("Require 0 <= m_s < m_h <= 1.")
        if any(abs(x - 1.0) > TOL for x in (self.p_0, self.p_1, self.reserve_return)):
            raise ValueError(
                "Version 4 is defined only for P0=P1=R_B=1. "
                "Non-unit prices require a separate nominal accounting closure."
            )
        if self.z <= 0 or self.z > self.income_h_0:
            raise ValueError("The displaced flow must be positive and affordable by H.")
        if not (0 <= self.q_0 <= 1) or not (0 <= self.delta_q <= 1):
            raise ValueError("Capacity and depreciation must lie in [0,1].")
        if self.damage_q < 0:
            raise ValueError("Capacity damage must be nonnegative.")
        if min(self.phi_high, self.phi_low) <= 0 or self.phi_high <= self.phi_low:
            raise ValueError("Require phi_high > phi_low > 0.")
        if min(self.a_operation, self.b_capacity, self.rho_o) <= 0:
            raise ValueError("Opportunity technology coefficients must be positive.")
        if self.consumption_h_0 > self.income_h_0 or self.consumption_s_0 > self.income_s_0:
            raise ValueError("Initial consumption cannot exceed initial income here.")

    @property
    def saving_h_0(self) -> float:
        return self.income_h_0 - self.consumption_h_0

    @property
    def saving_s_0(self) -> float:
        return self.income_s_0 - self.consumption_s_0

    @property
    def q_preinvestment(self) -> float:
        return (1.0 - self.delta_q) * self.q_0 - self.damage_q


@dataclass(frozen=True)
class FiscalInstrument:
    """Scalar reduction of rate, legal coverage, and compliance."""

    tax_rate: float
    legal_coverage: float
    compliance: float

    def validate(self) -> None:
        for name, value in (
            ("tax_rate", self.tax_rate),
            ("legal_coverage", self.legal_coverage),
            ("compliance", self.compliance),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must lie in [0,1].")

    @property
    def kappa_gross(self) -> float:
        return self.tax_rate * self.legal_coverage * self.compliance

    def legal_base(self, z: float) -> float:
        return self.legal_coverage * z

    def receipts(self, z: float) -> float:
        return self.tax_rate * self.compliance * self.legal_base(z)


@dataclass(frozen=True)
class Policy:
    name: str
    description: str
    fiscal: FiscalInstrument
    admin_cost: float
    transfer_h: float
    investment_q: float
    reserve_b0: float
    operation_x1: float
    reserve_b1: float
    unused_u0: float
    phi: float

    @property
    def kappa_gross(self) -> float:
        return self.fiscal.kappa_gross

    def tax(self, p: Parameters) -> float:
        return self.fiscal.receipts(p.z)

    def validate(self, p: Parameters) -> None:
        p.validate()
        self.fiscal.validate()
        fields = (
            self.admin_cost, self.transfer_h, self.investment_q, self.reserve_b0,
            self.operation_x1, self.reserve_b1, self.unused_u0, self.phi,
        )
        if min(fields) < -TOL:
            raise ValueError(f"{self.name}: policy quantities must be nonnegative.")
        tax = self.tax(p)
        if self.admin_cost > tax + TOL:
            raise ValueError(f"{self.name}: administration cannot exceed gross receipts.")
        net = tax - self.admin_cost
        use = self.transfer_h + self.investment_q + self.reserve_b0 + self.unused_u0
        if abs(net - use) > TOL:
            raise ValueError(f"{self.name}: date-0 public budget does not close.")
        if abs(self.reserve_b0 - self.operation_x1 - self.reserve_b1) > TOL:
            raise ValueError(f"{self.name}: date-1 reserve budget does not close at R_B=1.")


@dataclass(frozen=True)
class LedgerEntry:
    entry_id: str
    transaction_id: str
    date: int
    record_type: str
    entity: str
    counterparty: str
    account: str
    entry_role: str
    economic_class: str
    unit: str
    cash_change: float = 0.0
    asset_change: float = 0.0
    liability_change: float = 0.0
    direct_demand_category: str = ""
    note: str = ""

    @property
    def consolidation_value(self) -> float:
        if self.record_type == "cash":
            return self.cash_change
        return self.asset_change - self.liability_change

    def to_dict(self) -> Dict[str, object]:
        row = asdict(self)
        row["consolidation_value"] = self.consolidation_value
        return row


@dataclass(frozen=True)
class OpportunityRequirement:
    status: str
    service_required: float
    operation_min: float
    capacity_min: float
    investment_min: float
    reserve_min: float


@dataclass(frozen=True)
class FixedAllocationThresholds:
    """Conditional gate thresholds when a policy allocation is held fixed."""

    demand_m_h_max: float
    opportunity_phi_min: float
    demand_constant: float
    displaced_net_of_transfer: float
    required_capacity: float
    preinvestment_capacity: float
    service_required: float
    fixed_operation_service_ceiling: float
    opportunity_status: str


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    description: str
    tax: float
    net_public_resources: float
    income_h: float
    income_s: float
    consumption_h: float
    consumption_s: float
    saving_h: float
    saving_s: float
    assets_h_1: float
    assets_s_1: float
    delta_demand_0: float
    q_raw_1: float
    q_1: float
    service_1: float
    opportunity_1: float
    demand_gate: bool
    opportunity_gate: bool
    public_budget_residual_0: float
    reserve_budget_residual_1: float
    consolidated_cash_residual_0: float
    consolidated_cash_residual_1: float
    household_budget_residual_h: float
    household_budget_residual_s: float
    financial_counterpart_residual_0: float
    ledger_direct_demand_residual: float
    ledger_transaction_residual: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def project_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def opportunity_requirement(p: Parameters, phi: float) -> OpportunityRequirement:
    p.validate()
    if phi <= 0:
        raise ValueError("phi must be positive.")
    service_required = max(0.0, (p.opportunity_min - p.opportunity_0) / p.rho_o)
    if service_required <= TOL:
        return OpportunityRequirement("already_satisfied", 0.0, 0.0, 0.0, 0.0, 0.0)
    if service_required > p.b_capacity + TOL:
        return OpportunityRequirement(
            "technically_impossible", service_required, float("inf"), float("inf"),
            float("inf"), float("inf")
        )
    operation_min = service_required / p.a_operation
    capacity_min = service_required / p.b_capacity
    investment_min = max(0.0, capacity_min - p.q_preinvestment) / phi
    reserve_min = operation_min
    return OpportunityRequirement(
        "positive_feasible_target", service_required, operation_min, capacity_min,
        investment_min, reserve_min,
    )


def fixed_allocation_gate_thresholds(
    p: Parameters, policy: Policy
) -> FixedAllocationThresholds:
    """Derive the two gate boundaries for a fixed fiscal allocation.

    The demand boundary treats m_H as the varying local spending response while
    holding m_S and every policy flow fixed.  The opportunity boundary treats
    phi as the varying conversion coefficient while holding investment and the
    operating input fixed.  The function is intentionally conditional: it is
    not an optimization over policy instruments or an equilibrium comparative
    static.
    """
    policy.validate(p)
    displaced_net_of_transfer = p.z - policy.transfer_h
    if displaced_net_of_transfer <= TOL:
        raise ValueError("This diagnostic requires Z-y_T>0.")
    demand_constant = (
        p.m_s * (p.z - policy.tax(p))
        + p.d_admin * policy.admin_cost
        + p.d_investment * policy.investment_q
    )
    demand_m_h_max = demand_constant / displaced_net_of_transfer

    service_required = max(0.0, (p.opportunity_min - p.opportunity_0) / p.rho_o)
    fixed_operation_service_ceiling = p.a_operation * policy.operation_x1
    if service_required <= TOL:
        opportunity_phi_min = 0.0
        required_capacity = 0.0
        opportunity_status = "already_satisfied"
    elif service_required > p.b_capacity + TOL:
        opportunity_phi_min = float("inf")
        required_capacity = float("inf")
        opportunity_status = "technically_impossible"
    elif fixed_operation_service_ceiling + TOL < service_required:
        opportunity_phi_min = float("inf")
        required_capacity = service_required / p.b_capacity
        opportunity_status = "operation_insufficient"
    else:
        required_capacity = service_required / p.b_capacity
        capacity_gap = max(0.0, required_capacity - p.q_preinvestment)
        if capacity_gap <= TOL:
            opportunity_phi_min = 0.0
            opportunity_status = "capacity_already_sufficient"
        elif policy.investment_q <= TOL:
            opportunity_phi_min = float("inf")
            opportunity_status = "investment_insufficient"
        else:
            opportunity_phi_min = capacity_gap / policy.investment_q
            opportunity_status = "interior_threshold"

    return FixedAllocationThresholds(
        demand_m_h_max=demand_m_h_max,
        opportunity_phi_min=opportunity_phi_min,
        demand_constant=demand_constant,
        displaced_net_of_transfer=displaced_net_of_transfer,
        required_capacity=required_capacity,
        preinvestment_capacity=p.q_preinvestment,
        service_required=service_required,
        fixed_operation_service_ceiling=fixed_operation_service_ceiling,
        opportunity_status=opportunity_status,
    )


def direct_demand_formula(p: Parameters, policy: Policy) -> float:
    policy.validate(p)
    tax = policy.tax(p)
    return (
        -p.m_h * p.z + p.m_s * (p.z - tax) + p.m_h * policy.transfer_h
        + p.d_admin * policy.admin_cost + p.d_investment * policy.investment_q
    )


def build_ledger(p: Parameters, policy: Policy) -> List[LedgerEntry]:
    """Construct independent payer/receiver and asset/liability entries."""
    policy.validate(p)
    tax = policy.tax(p)
    entries: List[LedgerEntry] = []

    def cash(suffix: str, date: int, payer: str, receiver: str, amount: float,
             economic_class: str, demand_category: str = "", note: str = "") -> None:
        tx = f"{policy.name}-{suffix}"
        entries.extend([
            LedgerEntry(f"{tx}-P", tx, date, "cash", payer, receiver, "cash", "payer",
                        economic_class, UNIT, cash_change=-amount, note=note),
            LedgerEntry(f"{tx}-R", tx, date, "cash", receiver, payer, "cash", "receiver",
                        economic_class, UNIT, cash_change=amount,
                        direct_demand_category=demand_category, note=note),
        ])

    def balance(suffix: str, date: int, public_account: str, amount: float,
                direction: str, note: str) -> None:
        tx = f"{policy.name}-{suffix}"
        sign = 1.0 if direction == "create" else -1.0
        entries.extend([
            LedgerEntry(f"{tx}-A", tx, date, "balance_sheet", "public_sector",
                        "depository", public_account, "asset", "deposit_position", UNIT,
                        asset_change=sign * amount, note=note),
            LedgerEntry(f"{tx}-L", tx, date, "balance_sheet", "depository",
                        "public_sector", public_account.replace("asset", "liability"),
                        "liability", "deposit_position", UNIT,
                        liability_change=sign * amount, note=note),
        ])

    cash("D0-AUTOMATION", 0, "exposed_households_H", "owners_S", p.z,
         "automation_income_shift", note="Conditional liquid-income displacement")
    cash("D0-TAX", 0, "owners_S", "treasury", tax, "automation_receipts",
         note="Tax on the legally covered and compliant automation-income base")
    cash("D0-TRANSFER", 0, "treasury", "exposed_households_H", policy.transfer_h,
         "public_transfer", note="Transfer to the high-MPC exposed group")
    cash("D0-ADMIN", 0, "treasury", "administrative_supplier", policy.admin_cost,
         "public_purchase", "administration", "Administration purchased once")
    cash("D0-INVESTMENT", 0, "treasury", "capital_goods_supplier", policy.investment_q,
         "public_investment", "capacity_investment", "Capacity investment purchased once")
    cash("D0-RESERVE", 0, "treasury", "depository", policy.reserve_b0,
         "financial_deposit", note="Earmarked reserve; not date-0 current demand")
    cash("D0-UNUSED", 0, "treasury", "depository", policy.unused_u0,
         "financial_deposit", note="Unallocated public balance; not current demand")
    balance("D0-RESERVE-POSITION", 0, "earmarked_reserve_asset", policy.reserve_b0,
            "create", "Public deposit asset and matching issuer liability")
    balance("D0-UNUSED-POSITION", 0, "unused_balance_asset", policy.unused_u0,
            "create", "Unused public deposit and matching issuer liability")
    cash("D1-OPERATION", 1, "depository", "operating_input_supplier", policy.operation_x1,
         "public_purchase", "future_operation", "Operating input purchased once at date 1")
    balance("D1-RESERVE-REDEMPTION", 1, "earmarked_reserve_asset", policy.operation_x1,
            "redeem", "Reserve asset and deposit liability are redeemed together")
    return entries


def _sum_entries(entries: Iterable[LedgerEntry], **filters: object) -> float:
    total = 0.0
    for entry in entries:
        if all(getattr(entry, key) == value for key, value in filters.items()):
            total += entry.cash_change if entry.record_type == "cash" else entry.consolidation_value
    return total


def ledger_checks(p: Parameters, policy: Policy,
                  entries: List[LedgerEntry] | None = None) -> List[Dict[str, object]]:
    """Audit independent ledger entries against each other and the policy contract."""
    policy.validate(p)
    entries = list(build_ledger(p, policy) if entries is None else entries)
    checks: List[Dict[str, object]] = []

    def add(name: str, check_type: str, residual: float, evidence: str) -> None:
        checks.append({
            "scenario": policy.name, "check": name, "check_type": check_type,
            "residual": residual, "tolerance": 1.0e-8,
            "status": "PASS" if abs(residual) <= 1.0e-8 else "FAIL",
            "evidence": evidence,
        })

    cash_expected = {
        f"{policy.name}-D0-AUTOMATION": p.z,
        f"{policy.name}-D0-TAX": policy.tax(p),
        f"{policy.name}-D0-TRANSFER": policy.transfer_h,
        f"{policy.name}-D0-ADMIN": policy.admin_cost,
        f"{policy.name}-D0-INVESTMENT": policy.investment_q,
        f"{policy.name}-D0-RESERVE": policy.reserve_b0,
        f"{policy.name}-D0-UNUSED": policy.unused_u0,
        f"{policy.name}-D1-OPERATION": policy.operation_x1,
    }
    balance_expected = {
        f"{policy.name}-D0-RESERVE-POSITION": policy.reserve_b0,
        f"{policy.name}-D0-UNUSED-POSITION": policy.unused_u0,
        f"{policy.name}-D1-RESERVE-REDEMPTION": -policy.operation_x1,
    }
    by_transaction: Dict[str, List[LedgerEntry]] = {}
    for entry in entries:
        by_transaction.setdefault(entry.transaction_id, []).append(entry)

    for tx, expected in cash_expected.items():
        group = by_transaction.get(tx, [])
        add(f"{tx}:entry_count", "ledger_pairing", len(group) - 2,
            "Each cash transaction must have exactly one payer and one receiver entry")
        add(f"{tx}:pair_balance", "ledger_pairing", sum(x.cash_change for x in group),
            "Payer and receiver cash changes must offset")
        payer_amount = -sum(x.cash_change for x in group if x.entry_role == "payer")
        receiver_amount = sum(x.cash_change for x in group if x.entry_role == "receiver")
        add(f"{tx}:payer_matches_policy", "ledger_reconciliation", payer_amount - expected,
            "Payer entry is reconciled to the policy-generated expected amount")
        add(f"{tx}:receiver_matches_policy", "ledger_reconciliation", receiver_amount - expected,
            "Receiver entry is reconciled independently to the same expected amount")

    for tx, expected_change in balance_expected.items():
        group = by_transaction.get(tx, [])
        add(f"{tx}:entry_count", "ledger_pairing", len(group) - 2,
            "Each deposit operation must have an asset and a liability entry")
        add(f"{tx}:asset_liability_balance", "ledger_pairing",
            sum(x.consolidation_value for x in group),
            "Asset change minus liability change must be zero")
        assets = sum(x.asset_change for x in group if x.entry_role == "asset")
        liabilities = sum(x.liability_change for x in group if x.entry_role == "liability")
        add(f"{tx}:asset_matches_policy", "ledger_reconciliation", assets - expected_change,
            "Public asset entry is reconciled to the expected stock change")
        add(f"{tx}:liability_matches_policy", "ledger_reconciliation", liabilities - expected_change,
            "Issuer liability entry is reconciled independently")

    cash_0 = sum(x.cash_change for x in entries if x.record_type == "cash" and x.date == 0)
    cash_1 = sum(x.cash_change for x in entries if x.record_type == "cash" and x.date == 1)
    add("consolidated_cash_date_0", "cross_account_reconciliation", cash_0,
        "All recorded date-0 payer and receiver entries")
    add("consolidated_cash_date_1", "cross_account_reconciliation", cash_1,
        "All recorded date-1 payer and receiver entries")
    treasury_0 = _sum_entries(entries, record_type="cash", date=0, entity="treasury")
    add("public_budget_from_ledger", "cross_account_reconciliation", treasury_0,
        "Treasury receipts and uses are aggregated from ledger entries")
    h_net = _sum_entries(entries, record_type="cash", date=0, entity="exposed_households_H")
    s_net = _sum_entries(entries, record_type="cash", date=0, entity="owners_S")
    add("H_income_incidence_from_ledger", "cross_account_reconciliation",
        h_net - (-p.z + policy.transfer_h), "Ledger net cash versus H incidence")
    add("S_income_incidence_from_ledger", "cross_account_reconciliation",
        s_net - (p.z - policy.tax(p)), "Ledger net cash versus S incidence")
    admin_receipts = sum(
        x.cash_change for x in entries if x.record_type == "cash" and x.date == 0
        and x.entry_role == "receiver" and x.direct_demand_category == "administration"
    )
    investment_receipts = sum(
        x.cash_change for x in entries if x.record_type == "cash" and x.date == 0
        and x.entry_role == "receiver" and x.direct_demand_category == "capacity_investment"
    )
    add("administrative_purchase_counted_once", "cross_account_reconciliation",
        admin_receipts - policy.admin_cost, "Tagged receiver entries for administration")
    add("investment_purchase_counted_once", "cross_account_reconciliation",
        investment_receipts - policy.investment_q, "Tagged receiver entries for investment")
    ledger_demand = (
        p.m_h * h_net + p.m_s * s_net + p.d_admin * admin_receipts
        + p.d_investment * investment_receipts
    )
    add("direct_demand_formula_vs_ledger", "independent_formula_reconciliation",
        ledger_demand - direct_demand_formula(p, policy),
        "Formula versus household and supplier entries from the ledger")
    reserve_asset = sum(x.asset_change for x in entries if x.record_type == "balance_sheet"
                        and x.account == "earmarked_reserve_asset")
    reserve_liability = sum(x.liability_change for x in entries if x.record_type == "balance_sheet"
                            and x.account == "earmarked_reserve_liability")
    unused_asset = sum(x.asset_change for x in entries if x.record_type == "balance_sheet"
                       and x.account == "unused_balance_asset")
    unused_liability = sum(x.liability_change for x in entries if x.record_type == "balance_sheet"
                           and x.account == "unused_balance_liability")
    add("ending_reserve_asset", "stock_flow_reconciliation", reserve_asset - policy.reserve_b1,
        "Created reserve asset less redemption equals terminal reserve")
    add("ending_reserve_liability", "stock_flow_reconciliation", reserve_liability - policy.reserve_b1,
        "Issuer liability follows independently recorded entries")
    add("ending_unused_asset", "stock_flow_reconciliation", unused_asset - policy.unused_u0,
        "Unused balance remains as a public financial asset")
    add("ending_unused_liability", "stock_flow_reconciliation", unused_liability - policy.unused_u0,
        "Depository liability matches the unused public balance")
    known_ids = set(cash_expected) | set(balance_expected)
    add("no_unregistered_transactions", "ledger_completeness",
        len(set(by_transaction) - known_ids), "All transaction identifiers belong to the contract")
    add("unique_entry_ids", "ledger_completeness",
        len(entries) - len({x.entry_id for x in entries}), "Every entry has a unique identifier")
    return checks


def compute_scenario(p: Parameters, policy: Policy) -> ScenarioResult:
    policy.validate(p)
    tax = policy.tax(p)
    net_public = tax - policy.admin_cost
    delta_income_h = -p.z + policy.transfer_h
    delta_income_s = p.z - tax
    income_h = p.income_h_0 + delta_income_h
    income_s = p.income_s_0 + delta_income_s
    consumption_h = p.consumption_h_0 + p.m_h * delta_income_h
    consumption_s = p.consumption_s_0 + p.m_s * delta_income_s
    saving_h = p.saving_h_0 + (1.0 - p.m_h) * delta_income_h
    saving_s = p.saving_s_0 + (1.0 - p.m_s) * delta_income_s
    assets_h_1 = p.assets_h_0 + saving_h
    assets_s_1 = p.assets_s_0 + saving_s
    q_raw = p.q_preinvestment + policy.phi * policy.investment_q
    q_1 = project_unit(q_raw)
    service_1 = min(p.a_operation * policy.operation_x1, p.b_capacity * q_1)
    opportunity_1 = p.opportunity_0 + p.rho_o * service_1
    delta_demand = direct_demand_formula(p, policy)
    entries = build_ledger(p, policy)
    checks = ledger_checks(p, policy, entries)
    failed = [x for x in checks if x["status"] != "PASS"]
    if failed:
        raise AssertionError(f"{policy.name}: ledger audit failed: {failed[:3]}")

    def residual(name: str) -> float:
        return float(next(x["residual"] for x in checks if x["check"] == name))

    pair_residual = max(abs(float(x["residual"])) for x in checks
                        if x["check_type"] == "ledger_pairing")
    result = ScenarioResult(
        policy.name, policy.description, tax, net_public, income_h, income_s,
        consumption_h, consumption_s, saving_h, saving_s, assets_h_1, assets_s_1,
        delta_demand, q_raw, q_1, service_1, opportunity_1,
        delta_demand >= -TOL, opportunity_1 >= p.opportunity_min - TOL,
        residual("public_budget_from_ledger"), residual("ending_reserve_asset"),
        residual("consolidated_cash_date_0"), residual("consolidated_cash_date_1"),
        income_h - consumption_h - saving_h, income_s - consumption_s - saving_s,
        max(abs(residual("ending_reserve_asset") - residual("ending_reserve_liability")),
            abs(residual("ending_unused_asset") - residual("ending_unused_liability"))),
        residual("direct_demand_formula_vs_ledger"), pair_residual,
    )
    assert_result(p, policy, result)
    return result


def assert_result(p: Parameters, policy: Policy, result: ScenarioResult) -> None:
    residuals = [value for key, value in result.to_dict().items() if "residual" in key]
    if max(abs(float(x)) for x in residuals) > 1.0e-8:
        raise AssertionError(f"{policy.name}: an accounting check failed: {residuals}")
    if not 0 <= result.q_1 <= 1:
        raise AssertionError(f"{policy.name}: capacity outside [0,1].")
    if result.service_1 < -TOL or result.opportunity_1 < p.opportunity_0 - TOL:
        raise AssertionError(f"{policy.name}: invalid opportunity output.")
    if min(result.income_h, result.income_s, result.consumption_h, result.consumption_s) < -TOL:
        raise AssertionError(f"{policy.name}: negative income or consumption.")


def baseline_policies(p: Parameters) -> List[Policy]:
    full = FiscalInstrument(1.0, 1.0, 1.0)
    none = FiscalInstrument(0.0, 1.0, 1.0)
    return [
        Policy("A", "Automation without a public response", none, 0.0, 0.0,
               0.0, 0.0, 0.0, 0.0, 0.0, p.phi_high),
        Policy("B", "Net receipts transferred to exposed households", full, 1.0,
               19.0, 0.0, 0.0, 0.0, 0.0, 0.0, p.phi_high),
        Policy("C", "Transfer, investment, and future operation; high capacity", full,
               1.0, 12.0, 3.0, 4.0, 4.0, 0.0, 0.0, p.phi_high),
        Policy("D", "Same fiscal uses as C; low conversion capacity", full, 1.0,
               12.0, 3.0, 4.0, 4.0, 0.0, 0.0, p.phi_low),
    ]


def maximum_joint_demand(p: Parameters, tax_rate: float, admin_cost: float, phi: float,
                         legal_coverage: float = 1.0,
                         compliance: float = 1.0) -> Dict[str, float | str | bool]:
    """Solve the productive linear allocation used in the joint gate test."""
    p.validate()
    fiscal = FiscalInstrument(tax_rate, legal_coverage, compliance)
    fiscal.validate()
    req = opportunity_requirement(p, phi)
    tax = fiscal.receipts(p.z)
    resources = tax - admin_cost
    if req.status == "technically_impossible":
        return {"feasible": False, "status": req.status, "delta_demand_max": float("nan")}
    minimum_total = req.investment_min + req.reserve_min
    if resources + TOL < minimum_total:
        return {"feasible": False, "status": "fiscally_infeasible",
                "delta_demand_max": float("nan"), "minimum_total": minimum_total,
                "resources": resources}
    allocatable = resources - req.reserve_min
    investment_cap = 0.0 if p.q_preinvestment >= 1 else max(0.0, (1.0 - p.q_preinvestment) / phi)
    investment = (max(req.investment_min, min(investment_cap, allocatable))
                  if p.d_investment > p.m_h else req.investment_min)
    transfer = allocatable - investment
    base = -p.m_h * p.z + p.m_s * (p.z - tax) + p.d_admin * admin_cost
    delta_demand_max = base + p.m_h * transfer + p.d_investment * investment
    return {
        "feasible": True, "status": "opportunity_financeable",
        "delta_demand_max": delta_demand_max, "demand_gate": delta_demand_max >= -TOL,
        "minimum_total": minimum_total, "resources": resources,
        "investment": investment, "transfer": transfer, "reserve": req.reserve_min,
        "investment_min": req.investment_min, "tax_rate": tax_rate,
        "legal_coverage": legal_coverage, "compliance": compliance,
        "kappa_gross": fiscal.kappa_gross,
    }
