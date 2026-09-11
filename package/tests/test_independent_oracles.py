import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from book_repro.config import load_configuration, package_root
from book_repro.generation import generate_outputs
from book_repro.independent import run_independent_checks
from book_repro.pipeline import source_tree_hash
from book_repro.production_adapter import write_production_observations


class IndependentOracleTests(unittest.TestCase):
    def setUp(self):
        self.root = package_root()
        self.temporary = tempfile.TemporaryDirectory()
        self.run = Path(self.temporary.name) / "oracle-run"
        parameters, policies, settings = load_configuration(self.root)
        generate_outputs(
            self.run,
            self.root,
            parameters,
            policies,
            settings,
            {
                "run_schema_version": 2,
                "package_version": settings["package"]["package_version"],
                "manuscript_version": settings["package"]["manuscript_version"],
                "parameter_set_id": settings["package"]["parameter_set_id"],
                "source_tree_sha256": source_tree_hash(self.root),
                "configuration_files": settings["configuration_files"],
            },
        )
        write_production_observations(self.run, parameters, policies)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _rewrite(path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_all_independent_oracle_groups_pass(self):
        report = run_independent_checks(self.root, self.run)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["groups_total"], 14)
        self.assertEqual(report["groups_failed"], 0)
        self.assertEqual(report["heterogeneous_units_total"], 1929)
        self.assertEqual(report["coverage_counts_by_unit"]["optimization_vertices"], 7)
        self.assertFalse(report["oracle_separation"]["production_module_imported"])
        evidence = {item["id"]: item["evidence"] for item in report["checks"]}
        self.assertEqual(evidence["A05_exact_frontiers_and_inclusive_boundaries"]["m_H_star"], "1/2")
        self.assertEqual(evidence["A05_exact_frontiers_and_inclusive_boundaries"]["phi_star"], "73/300")
        self.assertEqual(evidence["A10_vertex_enumeration_with_and_without_cap"]["capped_optimum"], "-391/125")
        self.assertEqual(evidence["A10_vertex_enumeration_with_and_without_cap"]["uncapped_optimum"], "-2")
        self.assertTrue(evidence["A10_vertex_enumeration_with_and_without_cap"]["full_budget_enumerated"])
        self.assertFalse(
            evidence["C16_02_constructive_two_gate_separation"]["assumptions"]
            ["opportunity_witness"]["conversion_estimated_or_calculated_here"]
        )

    def _group(self, identifier: str) -> dict:
        report = run_independent_checks(self.root, self.run)
        return next(item for item in report["checks"] if item["id"] == identifier)

    def _mutate_csv(self, filename: str, key_field: str, key_value: str, field: str, value: str) -> None:
        path = self.run / "results" / filename
        rows = self._load_rows(path)
        next(row for row in rows if row[key_field] == key_value)[field] = value
        self._rewrite(path, rows)

    @staticmethod
    def _load_rows(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_p3_rejects_mutated_demand_frontier_without_reference_verifier(self):
        self._mutate_csv("fixed_policy_gate_thresholds.csv", "opportunity_status", "interior_threshold", "demand_m_h_max", "0.75")
        with patch("book_repro.verification.verify_results", side_effect=AssertionError("must not run")):
            check = self._group("A05_exact_frontiers_and_inclusive_boundaries")
        self.assertEqual(check["status"], "failed")
        self.assertTrue(any(issue.get("field") == "demand_m_h_max" for issue in check["evidence"]["issues"]))

    def test_p3_rejects_mutated_capacity_frontier(self):
        self._mutate_csv("fixed_policy_gate_thresholds.csv", "opportunity_status", "interior_threshold", "opportunity_phi_min", "0.9")
        check = self._group("A05_exact_frontiers_and_inclusive_boundaries")
        self.assertEqual(check["status"], "failed")
        self.assertTrue(any(issue.get("field") == "opportunity_phi_min" for issue in check["evidence"]["issues"]))

    def test_p3_rejects_mutated_investment_minimum(self):
        self._mutate_csv("analytical_conditions.csv", "capacity_case", "high", "I_min", "99")
        check = self._group("A07_minima_already_satisfied_and_ceiling")
        self.assertEqual(check["status"], "failed")
        self.assertTrue(any(issue.get("field") == "I_min" for issue in check["evidence"]["issues"]))

    def test_p3_rejects_mutated_optimal_value(self):
        self._mutate_csv("optimization_summary.csv", "case", "productive_investment_ceiling", "delta_demand_max", "99")
        check = self._group("A10_vertex_enumeration_with_and_without_cap")
        self.assertEqual(check["status"], "failed")
        self.assertTrue(any(issue.get("field") == "delta_demand_max" for issue in check["evidence"]["issues"]))

    def test_p3_rejects_mutated_optimal_allocation(self):
        self._mutate_csv("optimization_summary.csv", "case", "productive_investment_ceiling", "investment", "99")
        check = self._group("A10_vertex_enumeration_with_and_without_cap")
        self.assertEqual(check["status"], "failed")
        self.assertTrue(any(issue.get("field") == "investment" for issue in check["evidence"]["issues"]))

    def test_p3_rejects_each_missing_required_observed_file(self):
        cases = [
            ("results/fixed_policy_gate_thresholds.csv", "A05_exact_frontiers_and_inclusive_boundaries"),
            ("results/analytical_conditions.csv", "A07_minima_already_satisfied_and_ceiling"),
            ("results/optimization_summary.csv", "A10_vertex_enumeration_with_and_without_cap"),
            ("independent/production_observations.json", "A06_capacity_projection_corners"),
        ]
        for relative, identifier in cases:
            with self.subTest(relative=relative):
                path = self.run / relative
                original = path.read_bytes()
                path.unlink()
                try:
                    check = self._group(identifier)
                    self.assertEqual(check["status"], "failed")
                    self.assertIn("missing_observed_file", [item["kind"] for item in check["evidence"]["issues"]])
                finally:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(original)

    def test_p3_rejects_mutated_productive_edge_observations(self):
        path = self.run / "independent" / "production_observations.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        mutations = [
            ("projection", "A06_capacity_projection_corners", lambda d: d["projection"][3].__setitem__("projected", 0.9)),
            ("already_satisfied", "A07_minima_already_satisfied_and_ceiling", lambda d: d["opportunity_requirements"]["already_satisfied"].__setitem__("status", "wrong")),
            ("technical_limit", "A07_minima_already_satisfied_and_ceiling", lambda d: d["opportunity_requirements"]["technically_impossible"].__setitem__("investment_min", 0.0)),
            ("operation_insufficient", "A08_operation_insufficient_at_capacity_ceiling", lambda d: d["operation_insufficient"]["threshold"].__setitem__("opportunity_status", "interior_threshold")),
            ("finance_shortfall", "A09_zero_capture_and_finance_shortfall", lambda d: d["fiscal_edge_cases"]["finance_shortfall"].__setitem__("resources", 7.0)),
            ("zero_capture", "A09_zero_capture_and_finance_shortfall", lambda d: d["fiscal_edge_cases"]["zero_capture"].__setitem__("tax", 1.0)),
            ("constant_objective", "A11_constant_objective_equal_coefficients", lambda d: d["constant_objective"]["observations"][1].__setitem__("direct_demand", 1.0)),
        ]
        for name, identifier, mutate in mutations:
            with self.subTest(name=name):
                document = json.loads(json.dumps(original))
                mutate(document)
                path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
                check = self._group(identifier)
                self.assertEqual(check["status"], "failed")
                self.assertTrue(check["evidence"]["issues"])
        path.write_text(json.dumps(original, indent=2, sort_keys=True), encoding="utf-8")

    def test_oracle_rejects_mutated_receiver_counterparty(self):
        path = self.run / "results" / "constructive_case_ledger_entries.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        target = next(row for row in rows if row["entry_id"] == "E-D0-TRANSFER-R")
        target["counterparty"] = "wrong_counterparty"
        self._rewrite(path, rows)
        report = run_independent_checks(self.root, self.run)
        check = next(item for item in report["checks"] if item["id"] == "A04_rational_ledger_counterparties_and_deposits")
        self.assertEqual(check["status"], "failed")
        self.assertTrue(any("receiver_counterparty" in issue for item in check["evidence"] for issue in item["problems"]))

    def test_oracle_rejects_missing_deposit_obligation(self):
        path = self.run / "results" / "constructive_case_ledger_entries.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        target = next(row for row in rows if row["entry_id"] == "E-D0-RESERVE-POSITION-L")
        target["liability_change"] = "0"
        self._rewrite(path, rows)
        report = run_independent_checks(self.root, self.run)
        check = next(item for item in report["checks"] if item["id"] == "A04_rational_ledger_counterparties_and_deposits")
        self.assertEqual(check["status"], "failed")
        self.assertTrue(any("liability_obligation" in issue for item in check["evidence"] for issue in item["problems"]))


if __name__ == "__main__":
    unittest.main()
