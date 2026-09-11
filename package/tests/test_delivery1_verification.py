import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from book_repro.config import load_configuration, package_root
from book_repro.pipeline import source_tree_hash
from book_repro.verification import verify_results


class DeliveryOneVerificationTests(unittest.TestCase):
    def setUp(self):
        self.root = package_root()
        self.temporary = tempfile.TemporaryDirectory()
        self.run = Path(self.temporary.name) / "run"
        manifest = json.loads(
            (self.root / "reference" / "manifest.json").read_text(encoding="utf-8")
        )
        for item in manifest["files"]:
            source = self.root / item["reference_path"]
            target = self.run / item["generated_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        metadata = {
            "run_schema_version": 2,
            "package_version": load_configuration(self.root)[2]["package"]["package_version"],
            "manuscript_version": manifest["manuscript_version"],
            "parameter_set_id": manifest["parameter_set_id"],
            "source_tree_sha256": source_tree_hash(self.root),
            "configuration_files": load_configuration(self.root)[2]["configuration_files"],
        }
        (self.run / "results" / "run_metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_configuration_reconstructs_declared_cases(self):
        parameters, policies, settings = load_configuration(self.root)
        self.assertEqual([policy.name for policy in policies], list("ABCD"))
        self.assertEqual(settings["package"]["manuscript_version"], "v22")
        self.assertEqual(parameters.p_0, 1.0)

    def test_complete_written_file_set_passes(self):
        self.assertEqual(verify_results(
            self.root,
            self.run,
            expected_identity={
                "package_version": load_configuration(self.root)[2]["package"]["package_version"],
                "source_tree_sha256": source_tree_hash(self.root),
            },
        )["status"], "passed")

    def test_missing_file_is_rejected(self):
        (self.run / "results" / "scenarios.csv").unlink()
        report = verify_results(self.root, self.run)
        self.assertEqual(report["status"], "failed")
        issues = [issue["kind"] for check in report["checks"] for issue in check.get("issues", [])]
        self.assertIn("missing_generated_file", issues)

    def test_duplicate_row_is_rejected(self):
        path = self.run / "results" / "scenarios.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines + [lines[1]]) + "\n", encoding="utf-8")
        report = verify_results(self.root, self.run)
        issues = [issue["kind"] for check in report["checks"] for issue in check.get("issues", [])]
        self.assertIn("duplicate_key", issues)

    def test_unit_change_is_rejected(self):
        path = self.run / "results" / "parameters.csv"
        rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
        rows[0]["unit"] = "wrong unit"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        report = verify_results(self.root, self.run)
        issues = [issue for check in report["checks"] for issue in check.get("issues", [])]
        self.assertTrue(any(issue["kind"] == "exact_value" and issue.get("column") == "unit" for issue in issues))

    def test_numeric_alteration_is_rejected(self):
        path = self.run / "results" / "constructive_case.csv"
        rows = list(csv.DictReader(path.open("r", encoding="utf-8", newline="")))
        rows[0]["O_1"] = "5.25"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        report = verify_results(self.root, self.run)
        issues = [issue for check in report["checks"] for issue in check.get("issues", [])]
        self.assertTrue(any(issue["kind"] == "numeric_value" and issue.get("column") == "O_1" for issue in issues))

    def test_unexpected_result_file_is_rejected(self):
        (self.run / "results" / "unregistered.csv").write_text("x\n1\n", encoding="utf-8")
        report = verify_results(self.root, self.run)
        issues = [issue["kind"] for check in report["checks"] for issue in check.get("issues", [])]
        self.assertIn("unexpected_generated_files", issues)


if __name__ == "__main__":
    unittest.main()
