import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from book_repro.config import load_configuration, load_tolerances, package_root
from book_repro.pipeline import environment_report, reproduce, source_tree_hash
from book_repro.verification import sha256, verify_results, verify_run


class DeliveryTwoLocalClosureTests(unittest.TestCase):
    def setUp(self):
        self.root = package_root()
        self.temporary = tempfile.TemporaryDirectory()
        self.temp = Path(self.temporary.name)
        self.open_run = self.temp / "open-run"
        self._make_open_run(self.open_run)

    def tearDown(self):
        self.temporary.cleanup()

    def _make_open_run(self, target: Path) -> None:
        manifest = json.loads(
            (self.root / "reference" / "manifest.json").read_text(encoding="utf-8")
        )
        for item in manifest["files"]:
            source = self.root / item["reference_path"]
            destination = target / item["generated_path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        settings = load_configuration(self.root)[2]
        metadata = {
            "run_schema_version": 2,
            "package_version": settings["package"]["package_version"],
            "manuscript_version": manifest["manuscript_version"],
            "parameter_set_id": manifest["parameter_set_id"],
            "source_tree_sha256": source_tree_hash(self.root),
            "configuration_files": settings["configuration_files"],
        }
        (target / "results" / "run_metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )

    def _seal(self, target: Path) -> None:
        inputs = target / "inputs" / "config"
        inputs.mkdir(parents=True, exist_ok=True)
        settings = load_configuration(self.root)[2]
        for name in settings["configuration_files"]:
            shutil.copy2(self.root / "config" / name, inputs / name)
        verification = verify_results(
            self.root,
            target,
            expected_identity={
                "package_version": settings["package"]["package_version"],
                "source_tree_sha256": source_tree_hash(self.root),
            },
        )
        self.assertEqual(verification["status"], "passed")
        (target / "verification.json").write_text(
            json.dumps(verification, indent=2, sort_keys=True), encoding="utf-8"
        )
        metadata = json.loads(
            (target / "results" / "run_metadata.json").read_text(encoding="utf-8")
        )
        produced = {
            str(path.relative_to(target)).replace("\\", "/"): sha256(path)
            for path in sorted(target.rglob("*"))
            if path.is_file() and path.name not in {"run_report.json", "COMPLETE.json"}
        }
        report = {
            "run_schema_version": 2,
            "status": "passed",
            "started_utc": "2026-09-10T00:00:00+00:00",
            "finished_utc": "2026-09-10T00:00:01+00:00",
            "package_version": metadata["package_version"],
            "manuscript_version": metadata["manuscript_version"],
            "parameter_set_id": metadata["parameter_set_id"],
            "source_tree_sha256": metadata["source_tree_sha256"],
            "configuration_files": metadata["configuration_files"],
            "stages": {"verification": {"status": "passed"}},
            "produced_files": produced,
        }
        (target / "run_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
        complete = {
            "schema_version": 2,
            "status": "passed",
            "run_report_sha256": sha256(target / "run_report.json"),
            "completed_utc": report["finished_utc"],
        }
        (target / "COMPLETE.json").write_text(
            json.dumps(complete, indent=2, sort_keys=True), encoding="utf-8"
        )

    @staticmethod
    def _issue_kinds(report: dict) -> list[str]:
        if report.get("verification_scope") == "completed_run":
            checks = [
                *report["result_verification"]["checks"],
                *report["traceability"]["checks"],
            ]
        else:
            checks = report["checks"]
        return [issue["kind"] for check in checks for issue in check.get("issues", [])]

    def _package_copy(self, label: str) -> Path:
        target = self.temp / label
        shutil.copytree(self.root / "config", target / "config")
        shutil.copytree(self.root / "reference", target / "reference")
        shutil.copytree(self.root / "src", target / "src", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(self.root / "tests", target / "tests", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(self.root / "pyproject.toml", target / "pyproject.toml")
        return target

    def test_invalid_tolerances_fail_all_three_entry_points(self):
        for index, value in enumerate((float("nan"), float("inf"), -1.0e-9)):
            with self.subTest(value=repr(value)):
                copied = self._package_copy(f"invalid-tolerance-{index}")
                path = copied / "config" / "tolerances.json"
                document = json.loads(path.read_text(encoding="utf-8"))
                document["floating_point"]["atol"] = value
                path.write_text(json.dumps(document, indent=2), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "finite|nonnegative"):
                    load_tolerances(copied)
                self.assertEqual(environment_report(copied)["status"], "failed")
                with self.assertRaisesRegex(ValueError, "finite|nonnegative"):
                    verify_results(copied, self.open_run)
                destination = self.temp / f"invalid-reproduce-{index}"
                with self.assertRaisesRegex(RuntimeError, "Environment check failed"):
                    reproduce(destination, copied, "invalid tolerance regression")
                self.assertFalse((destination / "COMPLETE.json").exists())

    def test_rtol_and_tolerance_schema_types_are_validated(self):
        cases = (
            ("rtol", float("nan"), "finite"),
            ("rtol", float("inf"), "finite"),
            ("rtol", -1.0e-12, "nonnegative"),
            ("atol", "1e-10", "JSON number"),
            ("atol", True, "JSON number"),
        )
        for index, (field, value, message) in enumerate(cases):
            with self.subTest(field=field, value=repr(value)):
                copied = self._package_copy(f"invalid-tolerance-shape-{index}")
                path = copied / "config" / "tolerances.json"
                document = json.loads(path.read_text(encoding="utf-8"))
                document["floating_point"][field] = value
                path.write_text(json.dumps(document, indent=2), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    load_tolerances(copied)
        copied = self._package_copy("missing-tolerance-field")
        path = copied / "config" / "tolerances.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["floating_point"].pop("rtol")
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing fields"):
            load_tolerances(copied)

    def test_invalid_tolerance_cannot_mask_changed_E(self):
        path = self.open_run / "results" / "constructive_case.csv"
        rows = list(csv.reader(path.open("r", encoding="utf-8", newline="")))
        o1 = rows[0].index("O_1")
        rows[1][o1] = "5.25"
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)
        valid = verify_results(self.root, self.open_run)
        self.assertIn("numeric_value", self._issue_kinds(valid))
        copied = self._package_copy("nan-mask-probe")
        tolerance_path = copied / "config" / "tolerances.json"
        document = json.loads(tolerance_path.read_text(encoding="utf-8"))
        document["floating_point"]["atol"] = float("nan")
        tolerance_path.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "finite"):
            verify_results(copied, self.open_run)

    def test_csv_extra_cell_is_rejected_explicitly(self):
        path = self.open_run / "results" / "constructive_case.csv"
        rows = list(csv.reader(path.open("r", encoding="utf-8", newline="")))
        rows[1].append("UNREGISTERED_EXTRA_CELL")
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)
        report = verify_results(self.root, self.open_run)
        check = next(item for item in report["checks"] if item["id"] == "file_19_constructive_case_csv")
        issue = next(item for item in check["issues"] if item["kind"] == "csv_row_length")
        self.assertEqual(issue["direction"], "extra")
        self.assertEqual(issue["row_number"], 2)

    def test_csv_short_row_is_rejected_explicitly(self):
        path = self.open_run / "results" / "constructive_case.csv"
        rows = list(csv.reader(path.open("r", encoding="utf-8", newline="")))
        rows[1].pop()
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)
        report = verify_results(self.root, self.open_run)
        check = next(item for item in report["checks"] if item["id"] == "file_19_constructive_case_csv")
        issue = next(item for item in check["issues"] if item["kind"] == "csv_row_length")
        self.assertEqual(issue["direction"], "missing")
        self.assertEqual(issue["row_number"], 2)

    def test_csv_ambiguous_header_is_rejected(self):
        path = self.open_run / "results" / "constructive_case.csv"
        rows = list(csv.reader(path.open("r", encoding="utf-8", newline="")))
        rows[0][1] = rows[0][0]
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)
        report = verify_results(self.root, self.open_run)
        self.assertIn("csv_ambiguous_header", self._issue_kinds(report))

    def test_completed_run_chain_passes_and_is_read_only(self):
        self._seal(self.open_run)
        before = {
            str(path.relative_to(self.open_run)): sha256(path)
            for path in self.open_run.rglob("*") if path.is_file()
        }
        report = verify_run(self.root, self.open_run)
        after = {
            str(path.relative_to(self.open_run)): sha256(path)
            for path in self.open_run.rglob("*") if path.is_file()
        }
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["run_identity"]["relation_to_current_package"], "current")
        self.assertEqual(
            report["execution_status"]["completed_run_traceability"]["status"],
            "passed",
        )
        self.assertTrue(
            report["execution_status"]["completed_run_traceability"]
            ["executed_current_invocation"]
        )
        self.assertFalse(
            report["execution_status"]["independent_oracles_P3"]
            ["reexecuted_current_invocation"]
        )
        self.assertNotIn("completed_run_traceability", report["pending"])
        self.assertNotIn("independent_oracles_P3", report["pending"])
        self.assertEqual(before, after)

    def test_completed_run_detects_source_hash_mutation(self):
        self._seal(self.open_run)
        path = self.open_run / "results" / "run_metadata.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["source_tree_sha256"] = "0" * 64
        path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        report = verify_run(self.root, self.open_run)
        self.assertEqual(report["status"], "failed")
        self.assertIn("sealed_file_hash", self._issue_kinds(report))

    def test_completed_run_detects_missing_configuration_fields(self):
        self._seal(self.open_run)
        path = self.open_run / "results" / "run_metadata.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value.pop("configuration_files")
        path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        report = verify_run(self.root, self.open_run)
        self.assertEqual(report["status"], "failed")
        self.assertIn("metadata_missing_field", self._issue_kinds(report))

    def test_completed_run_detects_failed_report_status(self):
        self._seal(self.open_run)
        path = self.open_run / "run_report.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["status"] = "failed"
        path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        report = verify_run(self.root, self.open_run)
        self.assertEqual(report["status"], "failed")
        self.assertIn("run_report_status", self._issue_kinds(report))

    def test_completed_run_detects_completion_hash_mutation(self):
        self._seal(self.open_run)
        path = self.open_run / "COMPLETE.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["run_report_sha256"] = "0" * 64
        path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        report = verify_run(self.root, self.open_run)
        self.assertEqual(report["status"], "failed")
        self.assertIn("completion_report_hash", self._issue_kinds(report))

    def test_historical_run_is_identified_without_relabelling(self):
        self._seal(self.open_run)
        metadata_path = self.open_run / "results" / "run_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.pop("run_schema_version")
        metadata["source_tree_sha256"] = "1" * 64
        metadata["configuration_files"].pop("tolerances.json")
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        report_path = self.open_run / "run_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report.pop("run_schema_version")
        report.pop("configuration_files")
        report["source_tree_sha256"] = metadata["source_tree_sha256"]
        report["produced_files"] = {
            str(path.relative_to(self.open_run)).replace("\\", "/"): sha256(path)
            for path in sorted(self.open_run.rglob("*"))
            if path.is_file() and path.name not in {"run_report.json", "COMPLETE.json"}
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        complete_path = self.open_run / "COMPLETE.json"
        complete = json.loads(complete_path.read_text(encoding="utf-8"))
        complete.pop("schema_version")
        complete["run_report_sha256"] = sha256(report_path)
        complete_path.write_text(json.dumps(complete, indent=2, sort_keys=True), encoding="utf-8")
        checked = verify_run(self.root, self.open_run)
        self.assertEqual(checked["status"], "passed")
        self.assertTrue(checked["run_identity"]["legacy_run_schema"])
        self.assertEqual(checked["run_identity"]["relation_to_current_package"], "historical")

    @unittest.skipUnless(sys.platform == "win32", "Windows bootstrap contract")
    def test_bootstrap_stops_after_missing_local_dependency(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        self.assertIsNotNone(shell)
        requirement = self.temp / "missing-requirement.txt"
        requirement.write_text(
            "book-repro-deliberately-missing==999.0 "
            "--hash=sha256:0000000000000000000000000000000000000000000000000000000000000000\n",
            encoding="utf-8",
        )
        environment = self.temp / "bootstrap-failure-venv"
        process = subprocess.run(
            [
                str(shell), "-NoProfile", "-File", str(self.root / "bootstrap_windows.ps1"),
                "-VenvPath", str(environment), "-RequirementsPath", str(requirement),
            ],
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
        transcript = process.stdout + process.stderr
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("[2/4] Installing locked local dependencies", transcript)
        self.assertNotIn("[3/4] Installing the local project", transcript)
        self.assertNotIn("[4/4] Checking the installed environment", transcript)
        self.assertIn("install_dependencies failed", transcript)


if __name__ == "__main__":
    unittest.main()
