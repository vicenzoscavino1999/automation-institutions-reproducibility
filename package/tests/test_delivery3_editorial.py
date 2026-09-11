from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from book_repro.cli import parser
from book_repro.config import package_root
from book_repro.editorial import (
    _compiler_version,
    _conditional_figure,
    _font_contract,
    _pdf_page_count,
    _scenario_figure,
    _write_tables,
)
from book_repro.manuscript import check_book


class DeliveryThreeEditorialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = package_root()
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.run = self.work / "run"
        results = self.run / "results"
        results.mkdir(parents=True)
        config = self.run / "inputs" / "config"
        config.mkdir(parents=True)
        shutil.copy2(self.root / "config" / "benchmark.json", config / "benchmark.json")
        required = (
            "parameters.csv",
            "scenarios.csv",
            "constructive_case.csv",
            "analytical_conditions.csv",
            "optimization_summary.csv",
            "accounting_checks.csv",
            "constructive_case_accounting_checks.csv",
            "conditional_gate_regions.csv",
            "fixed_policy_gate_thresholds.csv",
        )
        for name in required:
            shutil.copy2(self.root / "reference" / "numeric" / name, results / name)
        independent = self.run / "independent"
        independent.mkdir()
        (independent / "oracle_results.json").write_text(
            json.dumps({
                "checks": [{
                    "id": "A05_exact_frontiers_and_inclusive_boundaries",
                    "evidence": {"m_H_star": "1/2", "phi_star": "73/300"},
                }]
            }),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_registry_has_required_primary_labels_and_metadata(self) -> None:
        registry = json.loads((self.root / "config" / "book_claims.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["manuscript_version"], "v22")
        self.assertEqual(len(registry["claims"]), 16)
        labels = {claim["latex_label"] for claim in registry["claims"] if claim["latex_label"]}
        required = {
            "eq:worked_capture_app", "eq:worked_public_budget_app",
            "eq:worked_reserve_budget_app", "eq:worked_households_app",
            "eq:worked_direct_demand_app", "eq:worked_capacity_app",
            "eq:worked_opportunity_app", "eq:worked_minima_app",
            "eq:worked_joint_financing_app", "tab:worked_cases_app",
            "fig:worked_gate_map_app", "eq:worked_mpc_frontier_app",
            "eq:worked_phi_frontier_app", "fig:worked_conditional_regions_app",
        }
        self.assertEqual(labels, required)
        for claim in registry["claims"]:
            for field in ("magnitude", "unit", "scenario", "sources", "printed_precision"):
                self.assertIn(field, claim)

    def test_cli_exposes_p4_interfaces(self) -> None:
        commands = parser()._subparsers._group_actions[0].choices
        self.assertIn("build-docs", commands)
        self.assertIn("check-book", commands)

    def test_compiler_version_ignores_windows_code_page_preamble(self) -> None:
        output = (
            "Initial Win CP for (console input, console output, system): (CP850, CP65001, CP1252)\n"
            "I changed them all to CP1252\n"
            "Latexmk, John Collins, 9 March 2026. Version 4.88\n"
        )
        with patch("book_repro.editorial.subprocess.run", return_value=CompletedProcess([], 0, output, "")):
            self.assertEqual(_compiler_version("latexmk"), "Latexmk, John Collins, 9 March 2026. Version 4.88")

    def test_pdf_page_count_uses_pdfinfo_metadata(self) -> None:
        pdf = self.work / "compressed.pdf"
        pdf.write_bytes(b"%PDF-1.7\n% object streams intentionally make byte counting unreliable\n")
        with (
            patch("book_repro.editorial.shutil.which", return_value="pdfinfo"),
            patch(
                "book_repro.editorial.subprocess.run",
                return_value=CompletedProcess([], 0, "Pages:           11\nPage size:       612 x 792 pts\n", ""),
            ),
        ):
            self.assertEqual(_pdf_page_count(pdf), 11)

    def test_generated_tables_use_unrounded_run_outputs(self) -> None:
        manifest = _write_tables(self.run, self.work / "tables")
        self.assertEqual(manifest["status"], "passed")
        cases = (self.work / "tables" / "cases_table.tex").read_text(encoding="utf-8")
        optimization = (self.work / "tables" / "optimization_table.tex").read_text(encoding="utf-8")
        closure = (self.work / "tables" / "household_closure.tex").read_text(encoding="utf-8")
        self.assertIn("B & 0.90 & 0.25 & 20 & 19", cases)
        self.assertIn("E & 0.45 & 0.25 & 20 & 12", cases)
        self.assertIn("Productive ceiling & -3.128", optimization)
        self.assertIn("Ceiling removed & -2.000", optimization)
        self.assertIn("C_{H0}=72", closure)
        self.assertIn("C_{S0}=8", closure)
        self.assertIn("(S_{H0},S_{S0})=(8,12)", closure)
        parameter_table = (self.work / "tables" / "parameters_table.tex").read_text(encoding="utf-8")
        self.assertIn(r"\caption{Synthetic parameters and units}", parameter_table)
        self.assertEqual(
            manifest["sources"]["inputs/config/benchmark.json"],
            hashlib.sha256((self.run / "inputs" / "config" / "benchmark.json").read_bytes()).hexdigest(),
        )

    def test_editorial_figure_coordinates_and_exact_frontiers(self) -> None:
        figures = self.work / "figures"
        figures.mkdir()
        font = _font_contract(self.root)
        scenario = _scenario_figure(self.run, figures / "scenario.pdf", font)
        conditional = _conditional_figure(self.run, figures / "conditional.pdf", font)
        point_b = next(row for row in scenario["coordinates"] if row["scenario"] == "B")
        self.assertAlmostEqual(point_b["direct_demand_margin"], 0.1)
        self.assertEqual(point_b["opportunity_margin"], -4.0)
        self.assertEqual(conditional["boundaries"]["m_H_exact"], "1/2")
        self.assertEqual(conditional["boundaries"]["phi_exact"], "73/300")
        self.assertEqual(conditional["grid_rows_checked"], 4095)
        self.assertIn(b"BitstreamVeraSans", (figures / "scenario.pdf").read_bytes())

    def test_conditional_figure_rejects_mutated_region(self) -> None:
        path = self.run / "results" / "conditional_gate_regions.csv"
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        rows[0]["demand_gate"] = "False" if rows[0]["demand_gate"] == "True" else "True"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        figures = self.work / "figures"
        figures.mkdir()
        with self.assertRaisesRegex(AssertionError, "disagree with exact frontiers"):
            _conditional_figure(self.run, figures / "conditional.pdf", _font_contract(self.root))

    def _table_registry_and_manuscript(self, mutate: bool = False) -> tuple[Path, Path]:
        tables = self.work / "tables"
        _write_tables(self.run, tables)
        table = (tables / "cases_table.tex").read_text(encoding="utf-8")
        if mutate:
            table = table.replace("-12.0", "-11.0", 1)
        manuscript = self.work / ("mutated.tex" if mutate else "clean.tex")
        manuscript.write_text(
            "\\begin{table}\n\\label{tab:test}\n" + table + "\\end{table}\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(manuscript.read_bytes()).hexdigest()
        registry = self.work / ("mutated_claims.json" if mutate else "clean_claims.json")
        registry.write_text(json.dumps({
            "schema_version": 1,
            "manuscript_version": "v22-test",
            "manuscript_sha256": digest,
            "claims": [{
                "id": "cases",
                "kind": "scenario_table",
                "latex_label": "tab:test",
                "magnitude": "A-E",
                "unit": "declared",
                "scenario": "A-E",
                "printed_precision": {"delta_D0_dir": 1},
                "sources": [],
            }],
        }), encoding="utf-8")
        return registry, manuscript

    def test_check_book_accepts_derived_presentation_and_is_read_only(self) -> None:
        registry, manuscript = self._table_registry_and_manuscript()
        report = check_book(self.root, manuscript, self.run, claims_path=registry, require_completed_run=False)
        self.assertEqual(report["status"], "passed")
        self.assertTrue(report["manuscript"]["read_only"])
        self.assertEqual(report["manuscript"]["sha256_before"], report["manuscript"]["sha256_after"])

    def test_check_book_rejects_altered_printed_value(self) -> None:
        registry, manuscript = self._table_registry_and_manuscript(mutate=True)
        report = check_book(self.root, manuscript, self.run, claims_path=registry, require_completed_run=False)
        self.assertEqual(report["status"], "failed")
        issues = report["claims"][0]["issues"]
        self.assertTrue(any(issue["kind"] == "scenario_presentation" for issue in issues))


if __name__ == "__main__":
    unittest.main()
