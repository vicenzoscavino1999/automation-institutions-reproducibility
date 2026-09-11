import math
import unittest
from dataclasses import replace

from book_repro.model import (
    FiscalInstrument,
    Parameters,
    baseline_policies,
    build_ledger,
    compute_scenario,
    direct_demand_formula,
    fixed_allocation_gate_thresholds,
    ledger_checks,
    maximum_joint_demand,
    opportunity_requirement,
)


class ReducedEconomyTests(unittest.TestCase):
    def setUp(self):
        self.p = Parameters()
        self.policies = baseline_policies(self.p)
        self.results = {x.name: compute_scenario(self.p, x) for x in self.policies}

    def test_manual_scenario_values(self):
        self.assertAlmostEqual(self.results["A"].delta_demand_0, -12.0)
        self.assertAlmostEqual(self.results["B"].delta_demand_0, 0.1)
        self.assertAlmostEqual(self.results["C"].delta_demand_0, -3.2)
        self.assertAlmostEqual(self.results["D"].delta_demand_0, -3.2)
        self.assertAlmostEqual(self.results["C"].q_1, 0.82)
        self.assertAlmostEqual(self.results["D"].q_1, 0.31)
        self.assertAlmostEqual(self.results["C"].opportunity_1, 5.0)
        self.assertAlmostEqual(self.results["D"].opportunity_1, 2.55)

    def test_gate_pattern(self):
        self.assertEqual(
            [(self.results[k].demand_gate, self.results[k].opportunity_gate) for k in "ABCD"],
            [(False, False), (True, False), (False, True), (False, False)],
        )

    def test_c_and_d_differ_only_in_phi(self):
        c, d = self.policies[2], self.policies[3]
        dc, dd = c.__dict__.copy(), d.__dict__.copy()
        for key in ("name", "description", "phi"):
            dc.pop(key)
            dd.pop(key)
        self.assertEqual(dc, dd)
        self.assertGreater(c.phi, d.phi)

    def test_all_accounting_residuals_are_zero(self):
        for result in self.results.values():
            for key, value in result.to_dict().items():
                if "residual" in key:
                    self.assertAlmostEqual(value, 0.0, places=10, msg=f"{result.name}: {key}")

    def test_scenario_b_closed_form(self):
        b = self.policies[1]
        expected = -(
            self.p.m_h - self.p.m_s
        ) * (self.p.z - b.kappa_gross * self.p.z) + (
            self.p.d_admin - self.p.m_h
        ) * b.admin_cost
        self.assertAlmostEqual(direct_demand_formula(self.p, b), expected)

    def test_opportunity_cases(self):
        already = replace(self.p, opportunity_min=self.p.opportunity_0)
        req0 = opportunity_requirement(already, already.phi_high)
        self.assertEqual(req0.status, "already_satisfied")
        self.assertEqual(req0.investment_min, 0.0)
        impossible = replace(
            self.p,
            opportunity_min=self.p.opportunity_0 + self.p.rho_o * self.p.b_capacity + 0.01,
        )
        req_inf = opportunity_requirement(impossible, impossible.phi_high)
        self.assertEqual(req_inf.status, "technically_impossible")
        self.assertTrue(math.isinf(req_inf.investment_min))

    def test_analytical_minima(self):
        high = opportunity_requirement(self.p, self.p.phi_high)
        low = opportunity_requirement(self.p, self.p.phi_low)
        self.assertAlmostEqual(high.service_required, 4.0)
        self.assertAlmostEqual(high.operation_min, 4.0)
        self.assertAlmostEqual(high.capacity_min, 0.8)
        self.assertAlmostEqual(high.investment_min, 2.92)
        self.assertAlmostEqual(high.reserve_min, 4.0)
        self.assertAlmostEqual(low.investment_min, 9.125)
        self.assertLessEqual(12.0 + high.investment_min + high.reserve_min, 19.0)
        self.assertGreater(12.0 + low.investment_min + low.reserve_min, 19.0)

    def test_joint_passage_is_not_feasible_at_baseline(self):
        joint = maximum_joint_demand(self.p, 1.0, 1.0, self.p.phi_high)
        self.assertTrue(joint["feasible"])
        self.assertFalse(joint["demand_gate"])
        self.assertAlmostEqual(joint["delta_demand_max"], -3.128)

    def test_fixed_policy_gate_thresholds(self):
        c = self.policies[2]
        thresholds = fixed_allocation_gate_thresholds(self.p, c)
        self.assertAlmostEqual(thresholds.demand_m_h_max, 0.5)
        self.assertAlmostEqual(thresholds.opportunity_phi_min, 0.73 / 3.0)
        at_boundary = replace(
            self.p,
            m_h=thresholds.demand_m_h_max,
            phi_high=thresholds.opportunity_phi_min,
        )
        boundary_policy = replace(c, phi=thresholds.opportunity_phi_min)
        result = compute_scenario(at_boundary, boundary_policy)
        self.assertAlmostEqual(result.delta_demand_0, 0.0)
        self.assertAlmostEqual(result.opportunity_1, self.p.opportunity_min)
        self.assertTrue(result.demand_gate)
        self.assertTrue(result.opportunity_gate)

    def test_fixed_policy_threshold_detects_insufficient_operation(self):
        c = self.policies[2]
        low_operation = replace(
            c,
            transfer_h=13.0,
            reserve_b0=3.0,
            operation_x1=3.0,
        )
        thresholds = fixed_allocation_gate_thresholds(self.p, low_operation)
        self.assertEqual(thresholds.opportunity_status, "operation_insufficient")
        self.assertTrue(math.isinf(thresholds.opportunity_phi_min))
        result = compute_scenario(self.p, low_operation)
        self.assertAlmostEqual(result.opportunity_1, 4.0)
        self.assertFalse(result.opportunity_gate)
        saturated_capacity = compute_scenario(
            self.p, replace(low_operation, phi=1.0)
        )
        self.assertAlmostEqual(saturated_capacity.q_1, 1.0)
        self.assertAlmostEqual(saturated_capacity.opportunity_1, 4.0)
        self.assertFalse(saturated_capacity.opportunity_gate)

    def test_fixed_policy_threshold_is_zero_when_objective_already_met(self):
        already_met = replace(
            self.p,
            q_0=0.0,
            opportunity_min=self.p.opportunity_0,
        )
        low_phi_policy = replace(self.policies[2], phi=0.001)
        thresholds = fixed_allocation_gate_thresholds(already_met, low_phi_policy)
        self.assertEqual(thresholds.opportunity_status, "already_satisfied")
        self.assertEqual(thresholds.opportunity_phi_min, 0.0)
        result = compute_scenario(already_met, low_phi_policy)
        self.assertAlmostEqual(result.opportunity_1, already_met.opportunity_0)
        self.assertTrue(result.opportunity_gate)

    def test_constructive_joint_passage_case(self):
        c = self.policies[2]
        constructive_parameters = replace(self.p, m_h=0.45)
        result = compute_scenario(constructive_parameters, c)
        self.assertAlmostEqual(result.delta_demand_0, 0.4)
        self.assertAlmostEqual(result.q_1, 0.82)
        self.assertAlmostEqual(result.opportunity_1, 5.0)
        self.assertTrue(result.demand_gate)
        self.assertTrue(result.opportunity_gate)

    def test_fiscal_instrument_decomposition(self):
        fiscal = FiscalInstrument(tax_rate=0.5, legal_coverage=0.8, compliance=0.75)
        self.assertAlmostEqual(fiscal.kappa_gross, 0.3)
        self.assertAlmostEqual(fiscal.legal_base(self.p.z), 16.0)
        self.assertAlmostEqual(fiscal.receipts(self.p.z), 6.0)

    def test_non_unit_future_price_is_rejected(self):
        outside_scope = replace(self.p, p_1=2.0)
        with self.assertRaisesRegex(ValueError, "P0=P1=R_B=1"):
            compute_scenario(outside_scope, self.policies[2])

    def test_mutated_receiver_entry_fails_audit(self):
        policy = self.policies[2]
        entries = build_ledger(self.p, policy)
        mutated = [
            replace(entry, cash_change=entry.cash_change + 1.0)
            if entry.entry_id == "C-D0-INVESTMENT-R" else entry
            for entry in entries
        ]
        failed = [row for row in ledger_checks(self.p, policy, mutated) if row["status"] == "FAIL"]
        self.assertTrue(any("D0-INVESTMENT" in row["check"] for row in failed))
        self.assertTrue(any(row["check"] == "investment_purchase_counted_once" for row in failed))

    def test_duplicate_counterparty_entry_fails_audit(self):
        policy = self.policies[2]
        entries = build_ledger(self.p, policy)
        receiver = next(x for x in entries if x.entry_id == "C-D0-ADMIN-R")
        duplicate = replace(receiver, entry_id="C-D0-ADMIN-R-DUP")
        failed = [row for row in ledger_checks(self.p, policy, entries + [duplicate])
                  if row["status"] == "FAIL"]
        self.assertTrue(any(row["check"] == "C-D0-ADMIN:entry_count" for row in failed))
        self.assertTrue(any(row["check"] == "administrative_purchase_counted_once" for row in failed))

    def test_missing_liability_entry_fails_audit(self):
        policy = self.policies[2]
        entries = [
            entry for entry in build_ledger(self.p, policy)
            if entry.entry_id != "C-D0-RESERVE-POSITION-L"
        ]
        failed = [row for row in ledger_checks(self.p, policy, entries) if row["status"] == "FAIL"]
        self.assertTrue(any(row["check"] == "C-D0-RESERVE-POSITION:entry_count" for row in failed))
        self.assertTrue(any(row["check"] == "ending_reserve_liability" for row in failed))


if __name__ == "__main__":
    unittest.main()
