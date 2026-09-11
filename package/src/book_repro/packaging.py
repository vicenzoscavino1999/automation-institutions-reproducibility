"""Assemble and verify the explicit local distribution."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .pipeline import source_tree_hash
from .verification import sha256, verify_run


FORBIDDEN_PARTS = {
    "build",
    ".git",
    "__pycache__",
    "seguimiento_reproducibilidad_v1",
    "revision_cierre_focal_p6_2026_09_11",
}
FORBIDDEN_TERMS = {
    "curriculum",
    "referee",
    "prompt",
    "agent_memory",
    "email",
    "springer_form",
}
DOCUMENT_REPORT = "build_docs_report.json"
POWERSHELL_GUIDE_PATHS = (
    "README.md",
    "RECEIVER_GUIDE_ES.md",
    "docs/ENVIRONMENT_RECOVERY_ES.md",
    "docs/REPRODUCTION_ES.md",
)
POWERSHELL_CONTINUATION_DEFECT = "\\`"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"Unsafe distribution path: {value!r}")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload_hash(root: Path, relative_paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(relative_paths):
        path = root / Path(*PurePosixPath(relative).parts)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def audit_powershell_document_text(text: str, relative_path: str) -> list[dict[str, Any]]:
    """Locate backslashes that would be passed to Docker before a PowerShell continuation."""

    issues: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        count = line.count(POWERSHELL_CONTINUATION_DEFECT)
        if count:
            issues.append({
                "kind": "powershell_continuation_backslash",
                "path": relative_path,
                "line": line_number,
                "count": count,
            })
    return issues


def audit_powershell_guides(package_root: Path) -> list[dict[str, Any]]:
    """Check the four distributed receiver guides before package assembly."""

    issues: list[dict[str, Any]] = []
    for relative in POWERSHELL_GUIDE_PATHS:
        path = package_root.resolve() / Path(*PurePosixPath(relative).parts)
        if not path.is_file():
            issues.append({"kind": "powershell_guide_missing", "path": relative})
            continue
        issues.extend(audit_powershell_document_text(path.read_text(encoding="utf-8"), relative))
    return issues


def load_inclusion_contract(package_root: Path) -> dict[str, Any]:
    """Load the exact-file allowlist and reject ambiguous or unsafe entries."""

    path = package_root.resolve() / "config" / "distribution_inclusion.json"
    document = _read_json(path)
    if document.get("schema_version") != 1:
        raise ValueError("distribution_inclusion.json schema_version must be 1.")
    if not isinstance(document.get("archive_root"), str):
        raise ValueError("The distribution archive_root must be a string.")
    _safe_relative(document["archive_root"])
    for field in ("source_files", "standalone_document_files"):
        values = document.get(field)
        if not isinstance(values, list) or not values:
            raise ValueError(f"{field} must be a non-empty exact-file list.")
        if len(values) != len(set(values)):
            raise ValueError(f"{field} contains duplicate paths.")
        for value in values:
            _safe_relative(value)
    return document


def _audit_member_names(names: list[str], archive_root: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if len(names) != len(set(names)):
        issues.append({"kind": "duplicate_archive_member"})
    prefix = archive_root.rstrip("/") + "/"
    for name in names:
        try:
            path = _safe_relative(name)
        except ValueError:
            issues.append({"kind": "unsafe_archive_member", "path": name})
            continue
        if not name.startswith(prefix):
            issues.append({"kind": "archive_member_outside_root", "path": name})
        lowered_parts = {part.lower() for part in path.parts}
        if lowered_parts & FORBIDDEN_PARTS:
            issues.append({"kind": "forbidden_archive_part", "path": name})
        lowered = name.lower()
        if any(term in lowered for term in FORBIDDEN_TERMS):
            issues.append({"kind": "forbidden_archive_term", "path": name})
        if lowered.endswith((".zip", ".tar", ".tar.gz")):
            issues.append({"kind": "nested_archive", "path": name})
        if "book_through_chapter_16_v22" in lowered:
            issues.append({"kind": "full_manuscript_included", "path": name})
    return issues


def _copy_exact(source_root: Path, destination_root: Path, paths: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in paths:
        posix = _safe_relative(relative)
        source = source_root / Path(*posix.parts)
        if not source.is_file():
            raise FileNotFoundError(f"Allowlisted file is missing: {source}")
        destination = destination_root / Path(*posix.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append({"path": relative, "bytes": destination.stat().st_size, "sha256": sha256(destination)})
    return records


def _write_zip(staging_parent: Path, archive_root: str, output: Path) -> None:
    root = staging_parent / archive_root
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda p: p.as_posix()):
            relative = path.relative_to(staging_parent).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2026, 9, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def verify_distribution_archive(archive_path: Path) -> dict[str, Any]:
    """Verify names and every embedded checksum without extracting the ZIP."""

    archive_path = archive_path.resolve()
    issues: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        if len(roots) != 1:
            issues.append({"kind": "archive_root_count", "observed": sorted(roots)})
            archive_root = ""
        else:
            archive_root = next(iter(roots))
            issues.extend(_audit_member_names(names, archive_root))
        for relative in POWERSHELL_GUIDE_PATHS:
            member = f"{archive_root}/{relative}"
            if member in names:
                try:
                    text = archive.read(member).decode("utf-8")
                except UnicodeDecodeError as error:
                    issues.append({
                        "kind": "powershell_guide_invalid_utf8",
                        "path": relative,
                        "message": str(error),
                    })
                else:
                    issues.extend(audit_powershell_document_text(text, relative))
        checksum_name = f"{archive_root}/CHECKSUMS.sha256"
        manifest_name = f"{archive_root}/DISTRIBUTION_MANIFEST.json"
        if checksum_name not in names:
            issues.append({"kind": "checksums_missing"})
            checksum_rows: list[str] = []
        else:
            checksum_rows = archive.read(checksum_name).decode("utf-8").splitlines()
        expected: dict[str, str] = {}
        for row in checksum_rows:
            if not row.strip():
                continue
            digest, separator, relative = row.partition("  ")
            if not separator or len(digest) != 64 or relative in expected:
                issues.append({"kind": "invalid_checksum_row", "row": row})
                continue
            expected[relative] = digest
        payload_names = {
            name.removeprefix(f"{archive_root}/") for name in names if name != checksum_name
        }
        if set(expected) != payload_names:
            issues.append({
                "kind": "checksum_member_set_mismatch",
                "missing": sorted(payload_names - set(expected)),
                "extra": sorted(set(expected) - payload_names),
            })
        for relative, expected_hash in expected.items():
            observed = hashlib.sha256(archive.read(f"{archive_root}/{relative}")).hexdigest()
            if observed != expected_hash:
                issues.append({"kind": "checksum_mismatch", "path": relative})
        manifest = _read_json_from_zip(archive, manifest_name, issues)
        if manifest:
            if manifest.get("archive_root") != archive_root:
                issues.append({"kind": "manifest_archive_root_mismatch"})
            declared = {
                item.get("path")
                for field in ("source_files", "standalone_document_files")
                for item in manifest.get(field, [])
                if isinstance(item, dict)
            }
            expected_declared = payload_names - {"DISTRIBUTION_MANIFEST.json"}
            if declared != expected_declared:
                issues.append({
                    "kind": "manifest_member_set_mismatch",
                    "missing": sorted(expected_declared - declared),
                    "extra": sorted(declared - expected_declared),
                })
            for field in ("source_files", "standalone_document_files"):
                for record in manifest.get(field, []):
                    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                        issues.append({"kind": "invalid_manifest_file_record", "field": field})
                        continue
                    relative = record["path"]
                    member = f"{archive_root}/{relative}"
                    if member not in names:
                        continue
                    data = archive.read(member)
                    observed_hash = hashlib.sha256(data).hexdigest()
                    if record.get("sha256") != observed_hash or record.get("bytes") != len(data):
                        issues.append({"kind": "manifest_file_identity_mismatch", "path": relative})
    return {
        "schema_version": 1,
        "status": "passed" if not issues else "failed",
        "archive": str(archive_path),
        "archive_sha256": sha256(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "members_total": len(names),
        "archive_root": archive_root,
        "issues": issues,
    }


def _read_json_from_zip(
    archive: zipfile.ZipFile, name: str, issues: list[dict[str, Any]]
) -> dict[str, Any] | None:
    try:
        return json.loads(archive.read(name).decode("utf-8"))
    except KeyError:
        issues.append({"kind": "distribution_manifest_missing"})
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        issues.append({"kind": "distribution_manifest_invalid", "message": str(error)})
    return None


def assemble_distribution(
    package_root: Path,
    run: Path,
    document: Path,
    output: Path,
) -> dict[str, Any]:
    """Build the exact ZIP selected for release; never mutate source or prior runs."""

    package_root = package_root.resolve()
    run = run.resolve()
    document = document.resolve()
    output = output.resolve()
    checksum_path = output.with_suffix(output.suffix + ".sha256")
    release_manifest_path = output.with_suffix(".manifest.json")
    for target in (output, checksum_path, release_manifest_path):
        if target.exists():
            raise FileExistsError(f"Distribution output already exists: {target}")
    output.parent.mkdir(parents=True, exist_ok=True)

    contract = load_inclusion_contract(package_root)
    guide_issues = audit_powershell_guides(package_root)
    if guide_issues:
        raise AssertionError(f"Receiver guide command audit failed: {guide_issues}")
    verification = verify_run(package_root, run)
    if verification["status"] != "passed":
        raise AssertionError("The source run failed verification.")
    if verification["run_identity"]["relation_to_current_package"] != "current":
        raise AssertionError("Packaging requires a run from the current source tree.")
    document_report_path = document / DOCUMENT_REPORT
    if not document_report_path.is_file():
        raise FileNotFoundError(f"Document report is missing: {document_report_path}")
    document_report = _read_json(document_report_path)
    if document_report.get("status") != "passed":
        raise AssertionError("The autonomous document did not pass its build checks.")
    run_report_hash = sha256(run / "run_report.json")
    if document_report.get("source_run_report_sha256") != run_report_hash:
        raise AssertionError("The autonomous document was not built from the selected run.")

    archive_root = contract["archive_root"]
    with tempfile.TemporaryDirectory(prefix="book-repro-p7-", dir=output.parent) as temporary:
        staging_parent = Path(temporary)
        staging = staging_parent / archive_root
        source_records = _copy_exact(package_root, staging, contract["source_files"])
        document_destination = staging / "standalone_example"
        document_records = _copy_exact(
            document, document_destination, contract["standalone_document_files"]
        )
        source_payload_hash = _payload_hash(staging, contract["source_files"])
        document_payload_hash = _payload_hash(
            document_destination, contract["standalone_document_files"]
        )
        manifest = {
            "schema_version": 1,
            "status": "assembled_local_distribution_candidate",
            "assembled_utc": _utc_now(),
            "archive_root": archive_root,
            "package_version": contract["package_version"],
            "manuscript_version": "v22",
            "manuscript_included": False,
            "development_source_tree_sha256": source_tree_hash(package_root),
            "source_payload_sha256": source_payload_hash,
            "document_payload_sha256": document_payload_hash,
            "source_run_report_sha256": run_report_hash,
            "source_files": source_records,
            "standalone_document_files": [
                {**record, "path": f"standalone_example/{record['path']}"}
                for record in document_records
            ],
            "exclusions": contract["exclusions"],
            "publication": {
                "public_repository": "not_run",
                "archival_deposit": "not_run",
                "doi": None,
            },
            "rights": "No new license is granted; see LICENSE_STATUS.md.",
        }
        manifest_path = staging / "DISTRIBUTION_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        embedded_manifest_hash = sha256(manifest_path)
        payload_files = sorted(
            path.relative_to(staging).as_posix()
            for path in staging.rglob("*")
            if path.is_file() and path.name != "CHECKSUMS.sha256"
        )
        checksum_text = "\n".join(
            f"{sha256(staging / Path(*PurePosixPath(relative).parts))}  {relative}"
            for relative in payload_files
        ) + "\n"
        (staging / "CHECKSUMS.sha256").write_text(checksum_text, encoding="utf-8", newline="\n")
        member_issues = _audit_member_names(
            [f"{archive_root}/{relative}" for relative in payload_files + ["CHECKSUMS.sha256"]],
            archive_root,
        )
        if member_issues:
            raise AssertionError(f"Distribution allowlist audit failed: {member_issues}")
        _write_zip(staging_parent, archive_root, output)

    archive_verification = verify_distribution_archive(output)
    if archive_verification["status"] != "passed":
        raise AssertionError(f"Assembled ZIP failed verification: {archive_verification['issues']}")
    checksum_path.write_text(f"{archive_verification['archive_sha256']}  {output.name}\n", encoding="utf-8", newline="\n")
    release_manifest = {
        "schema_version": 1,
        "status": "assembled_and_verified",
        "archive": output.name,
        "archive_sha256": archive_verification["archive_sha256"],
        "archive_bytes": archive_verification["archive_bytes"],
        "archive_members_total": archive_verification["members_total"],
        "embedded_manifest_sha256": embedded_manifest_hash,
        "development_source_tree_sha256": manifest["development_source_tree_sha256"],
        "source_payload_sha256": manifest["source_payload_sha256"],
        "document_payload_sha256": manifest["document_payload_sha256"],
        "source_run_report_sha256": run_report_hash,
        "checksum_file": checksum_path.name,
    }
    release_manifest_path.write_text(
        json.dumps(release_manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return {
        "schema_version": 1,
        "status": "passed",
        "archive": str(output),
        "archive_sha256": archive_verification["archive_sha256"],
        "archive_bytes": archive_verification["archive_bytes"],
        "members_total": archive_verification["members_total"],
        "checksum": str(checksum_path),
        "release_manifest": str(release_manifest_path),
        "source_tree_sha256": manifest["development_source_tree_sha256"],
        "source_payload_sha256": manifest["source_payload_sha256"],
        "document_payload_sha256": manifest["document_payload_sha256"],
        "source_run_verification": verification["status"],
        "document_build_verification": document_report["status"],
        "publication": manifest["publication"],
        "issues": [],
    }
