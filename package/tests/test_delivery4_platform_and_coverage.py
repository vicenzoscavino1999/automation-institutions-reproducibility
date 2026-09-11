from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from book_repro.cli import parser
from book_repro.config import package_root
from book_repro.coverage import coverage_report, validate_registry_data
from book_repro.offline import activate_offline_guard, restore_offline_guard
from book_repro.verification import normalized_text_sha256


class DeliveryFourPlatformAndCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = package_root()

    def test_cli_exposes_delivery_four_interfaces(self) -> None:
        commands = parser()._subparsers._group_actions[0].choices
        self.assertIn("compare-runs", commands)
        self.assertIn("coverage", commands)
        coverage_actions = {action.dest for action in commands["coverage"]._actions}
        self.assertIn("manuscript", coverage_actions)

    def test_offline_guard_rejects_socket_resolution_and_connection(self) -> None:
        with patch.dict(os.environ, {"BOOK_REPRO_OFFLINE": "1"}):
            token = activate_offline_guard()
            try:
                with self.assertRaisesRegex(PermissionError, "Network disabled"):
                    socket.getaddrinfo("example.invalid", 443)
                with self.assertRaisesRegex(PermissionError, "Network disabled"):
                    socket.socket().connect(("127.0.0.1", 9))
            finally:
                restore_offline_guard(token)

    def test_coverage_registry_is_complete_and_honest(self) -> None:
        report = coverage_report(self.root)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["validation_mode"], "structural_only")
        self.assertEqual(report["manuscript_validation"], "not_run")
        self.assertEqual(report["chapters_total"], 16)
        self.assertEqual(report["appendix_and_reference_units_total"], 15)
        self.assertGreaterEqual(report["formal_results_total"], 80)
        registry = json.loads((self.root / "config" / "coverage.json").read_text(encoding="utf-8"))
        self.assertIn("unimplemented_module", {
            coverage_class
            for unit in registry["units"]
            for coverage_class in unit["coverage_classes"]
        })
        text = json.dumps(registry).lower()
        self.assertNotIn("full hank simulation", text)

    def _coverage_generator(self):
        path = self.root / "scripts" / "generate_coverage_registry.py"
        specification = importlib.util.spec_from_file_location("coverage_registry_generator", path)
        self.assertIsNotNone(specification)
        self.assertIsNotNone(specification.loader)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module

    def test_citation_without_argument_is_not_promoted_to_support(self) -> None:
        generator = self._coverage_generator()
        text = (
            "\\begin{proposition} Claim.\\label{prop:synthetic_a}\\end{proposition}\n"
            "Later text merely cites Proposition~\\ref{prop:synthetic_a}.\n"
        )
        statement_end = text.index("\n")
        support = generator.support_locator(text, 0, statement_end, len(text), "prop:synthetic_a")
        self.assertEqual(support["status"], "pending")
        self.assertEqual(support["kind"], "support_pending")

    def test_absent_support_is_recorded_as_pending(self) -> None:
        generator = self._coverage_generator()
        text = "\\begin{proposition} Claim.\\label{prop:synthetic_b}\\end{proposition}\n"
        support = generator.support_locator(text, 0, len(text), len(text), "prop:synthetic_b")
        self.assertEqual(support["status"], "pending")
        self.assertIsNone(support["start_line"])
        self.assertIsNone(support["end_line"])

    def test_proof_after_another_result_is_not_assigned_to_the_first(self) -> None:
        generator = self._coverage_generator()
        text = (
            "\\begin{proposition} A.\\label{prop:synthetic_c}\\end{proposition}\n"
            "\\begin{proposition} B.\\label{prop:synthetic_d}\\end{proposition}\n"
            "\\begin{proof}This proves B.\\end{proof}\n"
        )
        first_end = text.index("\n")
        second_start = first_end + 1
        support = generator.support_locator(text, 0, first_end, second_start, "prop:synthetic_c")
        self.assertEqual(support["status"], "pending")

    def test_manuscript_backed_check_rejects_other_proof_and_invalid_lines(self) -> None:
        source = "\n".join([
            r"\begin{proposition}", r"\label{prop:a}", "Claim A.", r"\end{proposition}",
            r"\begin{proposition}", r"\label{prop:b}", "Claim B.", r"\end{proposition}",
            r"\begin{proof}", "Proof of B.", r"\end{proof}", "",
        ])
        with tempfile.TemporaryDirectory() as temporary:
            manuscript = Path(temporary) / "synthetic.tex"
            manuscript.write_text(source, encoding="utf-8")
            digest = hashlib.sha256(manuscript.read_bytes()).hexdigest()
            pending = {
                "status": "pending", "kind": "support_pending", "form": "not_applicable",
                "start_line": None, "end_line": None, "associated_label": "prop:b",
            }
            registry = {
                "schema_version": 2,
                "manuscript_sha256": digest,
                "units": [{"id": "chapter_01", "kind": "chapter", "number": 1, "coverage_classes": ["support_pending"]}],
                "formal_results": [
                    {
                        "id": "formal_001", "unit_id": "chapter_01", "environment": "proposition",
                        "latex_label": "prop:a", "statement_locator": {"start_line": 1, "end_line": 4},
                        "hypotheses": {"status": "located_in_formal_statement", "start_line": 1, "end_line": 4},
                        "dependencies": [], "support_class": "analytical_support_located",
                        "analytical_support": {
                            "status": "located", "kind": "own_proof", "form": "proof_environment",
                            "start_line": 9, "end_line": 11, "associated_label": "prop:a",
                        },
                    },
                    {
                        "id": "formal_002", "unit_id": "chapter_01", "environment": "proposition",
                        "latex_label": "prop:b", "statement_locator": {"start_line": 5, "end_line": 8},
                        "hypotheses": {"status": "located_in_formal_statement", "start_line": 5, "end_line": 8},
                        "dependencies": [], "support_class": "support_pending", "analytical_support": pending,
                    },
                ],
            }
            issue_kinds = {item["kind"] for item in validate_registry_data(registry, manuscript)}
            self.assertIn("proof_associated_with_other_result", issue_kinds)

            invalid = copy.deepcopy(registry)
            invalid["formal_results"][0]["analytical_support"]["end_line"] = 999999
            invalid_kinds = {item["kind"] for item in validate_registry_data(invalid, manuscript)}
            self.assertIn("invalid_support_line", invalid_kinds)

    def test_named_proof_heading_must_name_the_real_v22_result(self) -> None:
        """Regress the audited v22 intervals without distributing the manuscript."""

        lines = ["% omitted v22 line"] * 14104
        lines[2871:2875] = [
            r"\begin{proposition}[Cost reduction and direct displacement]",
            r"\label{prop:direct_displacement_ch4}",
            "At fixed factor prices and task productivities, direct displacement follows.",
            r"\end{proposition}",
        ]
        lines[14082] = r"\subsection*{Proof of Proposition~\ref{prop:direct_displacement_ch4}}"
        lines[14083:14095] = ["% correct proof body"] * 12
        lines[14099:14103] = [
            r"\subsection*{Proof of Characterization~\ref{prop:reinstatement_ch4}}",
            "",
            (
                r"Proposition~\ref{prop:direct_displacement_ch4} is used in the body "
                r"of the reinstatement proof. \hfill$\square$"
            ),
            "",
        ]
        source = "\n".join(lines)
        with tempfile.TemporaryDirectory() as temporary:
            manuscript = Path(temporary) / "identified_v22_excerpt_positions.tex"
            manuscript.write_text(source, encoding="utf-8")
            registry = json.loads((self.root / "config" / "coverage.json").read_text(encoding="utf-8"))
            target = copy.deepcopy(next(
                item for item in registry["formal_results"]
                if item["latex_label"] == "prop:direct_displacement_ch4"
            ))
            registry["formal_results"] = [target]
            registry["manuscript_sha256"] = hashlib.sha256(manuscript.read_bytes()).hexdigest()

            self.assertEqual(target["analytical_support"]["start_line"], 14083)
            self.assertEqual(target["analytical_support"]["end_line"], 14095)
            self.assertEqual(validate_registry_data(registry, manuscript), [])

            altered = copy.deepcopy(registry)
            altered_support = altered["formal_results"][0]["analytical_support"]
            altered_support["start_line"] = 14100
            altered_support["end_line"] = 14103
            issues = validate_registry_data(altered, manuscript)
            self.assertIn(
                {"kind": "named_proof_label_mismatch", "result": "formal_002"},
                issues,
            )

    def test_nine_audited_associations_are_explicit(self) -> None:
        registry = json.loads((self.root / "config" / "coverage.json").read_text(encoding="utf-8"))
        by_label = {item["latex_label"]: item["analytical_support"] for item in registry["formal_results"]}
        expected = {
            "prop:direct_displacement_ch4": ("own_proof", 14083),
            "prop:scale_ambiguity_ch4": ("adjacent_derivation", 2908),
            "prop:opportunity_value_ch6": ("argument_in_statement", 5551),
            "prop:mpc_exposure_decomposition_ch7": ("own_proof", 14571),
            "prop:aggregate_equivalence_ch7": ("argument_in_statement", 5861),
            "prop:fund_payout_incidence_ch9": ("argument_in_statement", 8029),
            "prop:local_revenue_ch10": ("adjacent_derivation", 8478),
            "prop:conditional_congestion_ch12": ("argument_in_statement", 10467),
            "prop:two_layer_dominance_ch15": ("argument_in_statement", 12780),
        }
        for label, (kind, start_line) in expected.items():
            with self.subTest(label=label):
                self.assertEqual(by_label[label]["status"], "located")
                self.assertEqual(by_label[label]["kind"], kind)
                self.assertEqual(by_label[label]["start_line"], start_line)

    def test_ci_declares_remote_status_and_omits_manuscript_check(self) -> None:
        workflow = (self.root / ".github" / "workflows" / "reproduce.yml").read_text(encoding="utf-8")
        self.assertIn("python -m book_repro reproduce", workflow)
        self.assertIn("BOOK_REPRO_OFFLINE", workflow)
        self.assertNotIn("python -m book_repro check-book", workflow)
        self.assertIn("check-book not_run", workflow)
        status = json.loads((self.root / "provenance" / "ci_status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["remote_execution"], "not_run")

    def test_docker_recipe_uses_pinned_amd64_base_and_two_targets(self) -> None:
        dockerfile = (self.root / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea", dockerfile)
        self.assertIn("FROM python-base AS runtime", dockerfile)
        self.assertIn("FROM runtime AS docs", dockerfile)
        self.assertIn("poppler-utils", dockerfile)
        self.assertIn("latexmk", dockerfile)

    def test_text_comparison_normalizes_only_platform_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crlf = root / "crlf.txt"
            lf = root / "lf.txt"
            changed = root / "changed.txt"
            crlf.write_bytes(b"alpha\r\nbeta\r\n")
            lf.write_bytes(b"alpha\nbeta\n")
            changed.write_bytes(b"alpha\ngamma\n")
            self.assertEqual(normalized_text_sha256(crlf), normalized_text_sha256(lf))
            self.assertNotEqual(normalized_text_sha256(crlf), normalized_text_sha256(changed))


if __name__ == "__main__":
    unittest.main()
