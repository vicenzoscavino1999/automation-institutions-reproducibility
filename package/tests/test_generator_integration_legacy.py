import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from book_repro import generation as run_example
from book_repro.config import load_configuration, package_root


class GeneratorIntegrationTests(unittest.TestCase):
    def test_constructive_case_mutation_blocks_output_publication(self):
        original_builder = run_example.build_ledger

        def altered_builder(parameters, policy):
            entries = original_builder(parameters, policy)
            if policy.name == "E":
                return [
                    replace(entry, cash_change=entry.cash_change + 1.0)
                    if entry.entry_id == "E-D0-INVESTMENT-R"
                    else entry
                    for entry in entries
                ]
            return entries

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            results = temporary_root / "results"
            figures = temporary_root / "figures"
            with (
                patch.object(run_example, "build_ledger", side_effect=altered_builder),
            ):
                with self.assertRaisesRegex(
                    AssertionError, "constructive_failed_checks"
                ) as caught:
                    parameters, policies, settings = load_configuration()
                    run_example.generate_outputs(
                        temporary_root,
                        package_root(),
                        parameters,
                        policies,
                        settings,
                        {},
                    )

            self.assertIn('"core_failed_checks": 0', str(caught.exception))
            self.assertIn('"constructive_failed_checks":', str(caught.exception))
            self.assertFalse(any(results.glob("*")))
            self.assertFalse(any(figures.glob("*")))


if __name__ == "__main__":
    unittest.main()
