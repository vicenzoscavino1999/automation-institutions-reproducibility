from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from book_repro.cli import parser
from book_repro.config import package_root
from book_repro.packaging import (
    audit_powershell_document_text,
    audit_powershell_guides,
    load_inclusion_contract,
    verify_distribution_archive,
)
from book_repro import __version__


class DeliveryFivePackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = package_root()

    def test_cli_exposes_p7_interfaces(self) -> None:
        commands = parser()._subparsers._group_actions[0].choices
        self.assertIn("package", commands)
        self.assertIn("verify-package", commands)

    def test_active_distribution_version_is_coherent(self) -> None:
        contract = load_inclusion_contract(self.root)
        citation = (self.root / "CITATION.cff").read_text(encoding="utf-8")
        package = json.loads((self.root / "config" / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(__version__, "0.1.2")
        self.assertEqual(contract["package_version"], "0.1.2")
        self.assertEqual(contract["archive_root"], "automation-institutions-reproducibility-0.1.2")
        self.assertEqual(package["package_version"], "0.1.2")
        self.assertIn("version: 0.1.2", citation)

    def test_receiver_documents_do_not_depend_on_internal_milestones(self) -> None:
        paths = [
            self.root / "README.md",
            self.root / "RECEIVER_GUIDE_ES.md",
            self.root / "docs" / "REPRODUCTION_ES.md",
            self.root / "docs" / "FINAL_DISTRIBUTION_ES.md",
            self.root / "docs" / "ENVIRONMENT_RECOVERY_ES.md",
            self.root / "locks" / "environment.json",
            self.root / "provenance" / "docker_environment.json",
            self.root / "THIRD_PARTY_NOTICES.md",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("HITO_04", combined)
        self.assertNotIn("HITO_05", combined)
        self.assertNotIn("seguimiento_reproducibilidad", combined)
        self.assertIn("book-repro-runtime:0.1.2", combined)
        self.assertIn("book-repro-docs:0.1.2", combined)

    def test_receiver_powershell_continuations_are_docker_safe(self) -> None:
        self.assertEqual(audit_powershell_guides(self.root), [])
        guide = (self.root / "RECEIVER_GUIDE_ES.md").read_text(encoding="utf-8")
        self.assertIn("`\n", guide)
        altered = guide.replace("`\n", "\\`\n", 1)
        issues = audit_powershell_document_text(altered, "RECEIVER_GUIDE_ES.md")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["kind"], "powershell_continuation_backslash")

    def test_exact_allowlist_exists_and_excludes_internal_material(self) -> None:
        contract = load_inclusion_contract(self.root)
        files = contract["source_files"]
        self.assertEqual(len(files), len(set(files)))
        for relative in files:
            with self.subTest(relative=relative):
                self.assertTrue((self.root / relative).is_file())
                lowered = relative.lower()
                self.assertNotIn("build/", lowered)
                self.assertNotIn(".venv", lowered)
                self.assertNotIn("book_through_chapter_16_v22", lowered)
                self.assertNotIn("referee", lowered)
                self.assertNotIn("prompt", lowered)
        required = {
            "README.md",
            "RECEIVER_GUIDE_ES.md",
            "METHODS.md",
            "Dockerfile",
            "config/coverage.json",
            "docs/example_EN.tex",
            "docs/ENVIRONMENT_RECOVERY_ES.md",
            "docs/FINAL_DISTRIBUTION_ES.md",
            "reference/manifest.json",
            "src/book_repro/packaging.py",
            "tests/test_delivery5_packaging.py",
        }
        self.assertTrue(required.issubset(set(files)))

    def _write_archive(
        self,
        root: Path,
        *,
        corrupt: bool = False,
        unsafe: bool = False,
        payload: bytes = b"reproducible payload\n",
    ) -> Path:
        archive_root = "automation-institutions-reproducibility-0.1.2"
        manifest = json.dumps({
            "archive_root": archive_root,
            "source_files": [{
                "path": "README.md",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }],
            "standalone_document_files": [],
        }).encode("utf-8")
        checksums = (
            f"{hashlib.sha256(manifest).hexdigest()}  DISTRIBUTION_MANIFEST.json\n"
            f"{hashlib.sha256(payload).hexdigest()}  README.md\n"
        ).encode("utf-8")
        path = root / "candidate.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(f"{archive_root}/DISTRIBUTION_MANIFEST.json", manifest)
            archive.writestr(f"{archive_root}/README.md", b"changed\n" if corrupt else payload)
            archive.writestr(f"{archive_root}/CHECKSUMS.sha256", checksums)
            if unsafe:
                archive.writestr(f"{archive_root}/../agent_memory.txt", b"private")
        return path

    def test_archive_verifier_accepts_exact_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = verify_distribution_archive(self._write_archive(Path(temporary)))
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["issues"], [])

    def test_archive_verifier_rejects_checksum_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = verify_distribution_archive(
                self._write_archive(Path(temporary), corrupt=True)
            )
            self.assertEqual(report["status"], "failed")
            self.assertIn("checksum_mismatch", {item["kind"] for item in report["issues"]})

    def test_archive_verifier_rejects_unsafe_or_internal_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = verify_distribution_archive(
                self._write_archive(Path(temporary), unsafe=True)
            )
            self.assertEqual(report["status"], "failed")
            kinds = {item["kind"] for item in report["issues"]}
            self.assertTrue({"unsafe_archive_member", "forbidden_archive_term"} & kinds)

    def test_archive_verifier_rejects_self_consistent_continuation_defect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = verify_distribution_archive(
                self._write_archive(
                    Path(temporary),
                    payload=b"docker run --rm \\`\n  image:tag\n",
                )
            )
            self.assertEqual(report["status"], "failed")
            self.assertIn(
                "powershell_continuation_backslash",
                {item["kind"] for item in report["issues"]},
            )


if __name__ == "__main__":
    unittest.main()
