import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from book_repro.config import load_configuration, package_root
from book_repro.pipeline import source_tree_hash
from book_repro.verification import verify_results


class AdversarialMutationTests(unittest.TestCase):
    def setUp(self):
        self.root = package_root()
        self.temporary = tempfile.TemporaryDirectory()
        self.run = Path(self.temporary.name) / "mutated-run"
        manifest = json.loads((self.root / "reference" / "manifest.json").read_text(encoding="utf-8"))
        for item in manifest["files"]:
            source = self.root / item["reference_path"]
            target = self.run / item["generated_path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        settings = load_configuration(self.root)[2]
        metadata = {
            "run_schema_version": 2,
            "package_version": manifest["package_version"],
            "manuscript_version": manifest["manuscript_version"],
            "parameter_set_id": manifest["parameter_set_id"],
            "source_tree_sha256": source_tree_hash(self.root),
            "configuration_files": settings["configuration_files"],
        }
        (self.run / "results" / "run_metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _load(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _save(path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def _issues(self) -> list[dict]:
        report = verify_results(self.root, self.run)
        self.assertEqual(report["status"], "failed")
        return [issue for check in report["checks"] for issue in check.get("issues", [])]

    def test_mutation_E_value_has_numeric_diagnostic(self):
        path = self.run / "results" / "constructive_case.csv"
        rows = self._load(path)
        rows[0]["O_1"] = "5.25"
        self._save(path, rows)
        self.assertTrue(any(item["kind"] == "numeric_value" and item.get("column") == "O_1" for item in self._issues()))

    def test_mutation_receiver_has_exact_diagnostic(self):
        path = self.run / "results" / "constructive_case_ledger_entries.csv"
        rows = self._load(path)
        next(row for row in rows if row["entry_id"] == "E-D0-TRANSFER-R")["counterparty"] = "wrong_counterparty"
        self._save(path, rows)
        self.assertTrue(any(item["kind"] == "exact_value" and item.get("column") == "counterparty" for item in self._issues()))

    def test_mutation_deposit_obligation_has_numeric_diagnostic(self):
        path = self.run / "results" / "constructive_case_ledger_entries.csv"
        rows = self._load(path)
        next(row for row in rows if row["entry_id"] == "E-D0-RESERVE-POSITION-L")["liability_change"] = "0"
        self._save(path, rows)
        self.assertTrue(any(item["kind"] == "numeric_value" and item.get("column") == "liability_change" for item in self._issues()))

    def test_mutation_missing_row_is_rejected(self):
        path = self.run / "results" / "scenarios.csv"
        rows = self._load(path)[1:]
        self._save(path, rows)
        self.assertIn("missing_rows", [item["kind"] for item in self._issues()])

    def test_mutation_duplicate_row_is_rejected(self):
        path = self.run / "results" / "scenarios.csv"
        rows = self._load(path)
        self._save(path, rows + [dict(rows[0])])
        self.assertIn("duplicate_key", [item["kind"] for item in self._issues()])

    def test_mutation_unit_is_rejected_exactly(self):
        path = self.run / "results" / "parameters.csv"
        rows = self._load(path)
        rows[0]["unit"] = "wrong unit"
        self._save(path, rows)
        self.assertTrue(any(item["kind"] == "exact_value" and item.get("column") == "unit" for item in self._issues()))

    def test_mutation_classification_is_rejected_exactly(self):
        path = self.run / "results" / "constructive_case_ledger_entries.csv"
        rows = self._load(path)
        rows[0]["economic_class"] = "wrong_class"
        self._save(path, rows)
        self.assertTrue(any(item["kind"] == "exact_value" and item.get("column") == "economic_class" for item in self._issues()))

    def test_mutation_missing_file_is_rejected(self):
        (self.run / "results" / "scenarios.csv").unlink()
        self.assertIn("missing_generated_file", [item["kind"] for item in self._issues()])

    def test_mutation_text_hash_is_rejected(self):
        path = self.run / "results" / "scenarios_table.tex"
        path.write_text(path.read_text(encoding="utf-8") + "% mutation\n", encoding="utf-8")
        self.assertIn("hash_mismatch", [item["kind"] for item in self._issues()])

    def test_mutation_unexpected_file_is_rejected(self):
        (self.run / "results" / "unexpected.csv").write_text("x\n1\n", encoding="utf-8")
        self.assertIn("unexpected_generated_files", [item["kind"] for item in self._issues()])

    def test_mutation_key_is_rejected(self):
        path = self.run / "results" / "scenarios.csv"
        rows = self._load(path)
        rows[0]["scenario"] = "AX"
        self._save(path, rows)
        kinds = [item["kind"] for item in self._issues()]
        self.assertIn("missing_rows", kinds)
        self.assertIn("extra_rows", kinds)

    def test_mutation_nan_is_rejected_as_nonfinite(self):
        path = self.run / "results" / "constructive_case.csv"
        rows = self._load(path)
        rows[0]["O_1"] = "NaN"
        self._save(path, rows)
        self.assertIn("nonfinite", [item["kind"] for item in self._issues()])

    def test_mutation_infinity_is_rejected_as_nonfinite(self):
        path = self.run / "results" / "constructive_case.csv"
        rows = self._load(path)
        rows[0]["O_1"] = "Infinity"
        self._save(path, rows)
        self.assertIn("nonfinite", [item["kind"] for item in self._issues()])


if __name__ == "__main__":
    unittest.main()
