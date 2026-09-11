"""Build the static P6 coverage registry from the identified v22 source."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from book_repro.coverage import validate_registry_data


FORMAL = (
    "proposition|lemma|corollary|accountingresult|diagnostic|characterization|"
    "sufficientcondition|interfacelemma|invarianceresult"
)

P3_BY_LABEL = {
    "prop:collection_execution_no_go_ch16": "C16_01_collection_execution_bound",
    "prop:two_gate_separation_ch16": "C16_02_constructive_two_gate_separation",
    "prop:primitive_capacity_trap_ch16": "C16_03_primitive_capacity_trap_finite_check",
}

# These source-backed classifications close the nine associations identified by
# the independent P6 audit.  The line spans refer to the identified v22 source.
# Two further cases (direct displacement and the MPC decomposition) are found by
# their exact named proof headings and therefore need no override.
SUPPORT_OVERRIDES = {
    "prop:scale_ambiguity_ch4": {
        "kind": "adjacent_derivation", "start_line": 2908, "end_line": 2920,
        "basis": "The signed displacement-scale decomposition immediately precedes and enters the formal statement.",
    },
    "prop:opportunity_value_ch6": {
        "kind": "argument_in_statement", "start_line": 5551, "end_line": 5560,
        "basis": "The set-inclusion argument is stated inside the formal result.",
    },
    "prop:aggregate_equivalence_ch7": {
        "kind": "argument_in_statement", "start_line": 5861, "end_line": 5863,
        "basis": "The two-household sign-reversal construction is contained in the statement.",
    },
    "prop:fund_payout_incidence_ch9": {
        "kind": "argument_in_statement", "start_line": 8029, "end_line": 8058,
        "basis": "The local differentiation and finite arc-propensity arguments are contained in the statement.",
    },
    "prop:local_revenue_ch10": {
        "kind": "adjacent_derivation", "start_line": 8478, "end_line": 8505,
        "basis": "The product-rule identities precede the result and their accounting justification follows it.",
    },
    "prop:conditional_congestion_ch12": {
        "kind": "argument_in_statement", "start_line": 10467, "end_line": 10469,
        "basis": "The chain-rule sign argument and its branch conditions are inside the statement.",
    },
    "prop:two_layer_dominance_ch15": {
        "kind": "argument_in_statement", "start_line": 12780, "end_line": 12783,
        "basis": "The sufficient conditions and ranking implication are stated together; the later proof belongs to a different result.",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("--", "-")).strip()


def parse_units(text: str) -> list[dict]:
    appendix_start = text.index(r"\appendix")
    main_pattern = re.compile(r"\\chapter(?!\*)\s*(?:\[[^\]]*\]\s*)?\{([^{}]*)\}", re.S)
    units: list[dict] = []
    main_number = 0
    appendix_number = 0
    for match in main_pattern.finditer(text):
        title = clean_title(match.group(1))
        if match.start() < appendix_start:
            main_number += 1
            unit = {
                "id": f"chapter_{main_number:02d}",
                "kind": "chapter",
                "number": main_number,
                "title": title,
                "start_line": line_number(text, match.start()),
            }
            if main_number <= 2:
                classes = ["conceptual_explanation"]
            elif main_number == 3:
                classes = ["conceptual_explanation", "unimplemented_module"]
            elif main_number == 16:
                classes = ["analytical_support_located", "finite_computational_check"]
            else:
                classes = ["analytical_support_located", "unimplemented_module"]
            unit["coverage_classes"] = classes
        else:
            appendix_number += 1
            letter = chr(64 + appendix_number)
            unit = {
                "id": f"appendix_{letter}",
                "kind": "appendix",
                "letter": letter,
                "title": title,
                "start_line": line_number(text, match.start()),
                "coverage_classes": (
                    ["reproduced_numeric_result", "finite_computational_check"]
                    if letter == "A" else ["analytical_support_located"]
                ),
            }
        unit["source_position"] = match.start()
        units.append(unit)
    reference = re.search(r"\\chapter\*\{Reference tables: notation and interfaces\}", text)
    if reference:
        units.append({
            "id": "reference_tables",
            "kind": "reference_tables",
            "title": "Reference tables: notation and interfaces",
            "start_line": line_number(text, reference.start()),
            "source_position": reference.start(),
            "coverage_classes": ["conceptual_explanation"],
        })
    return units


def unit_for(position: int, units: list[dict]) -> dict:
    eligible = [unit for unit in units if unit["source_position"] <= position]
    return max(eligible, key=lambda unit: unit["source_position"])


def _named_proof(text: str, label: str) -> dict | None:
    heading = re.compile(
        rf"\\(?:chapter|section|subsection)\*?\{{[^\n{{}}]*(?:Proof|proof|Derivation|derivation)"
        rf"[^\n{{}}]*\\ref\{{{re.escape(label)}\}}[^\n{{}}]*\}}"
    )
    match = heading.search(text)
    if not match:
        return None
    next_heading = re.search(r"\\(?:chapter|section|subsection)\*?\{", text[match.end():])
    end_position = match.end() + next_heading.start() if next_heading else len(text)
    return {
        "status": "located",
        "kind": "own_proof",
        "form": "named_proof_section",
        "start_line": line_number(text, match.start()),
        "end_line": max(line_number(text, end_position) - 1, line_number(text, match.start())),
        "associated_label": label,
        "basis": "An exact proof heading names this formal result.",
    }


def _adjacent_proof_environment(
    text: str, statement_end: int, next_statement: int, label: str
) -> dict | None:
    region = text[statement_end:next_statement]
    start_match = re.search(r"\\begin\{proof\}", region)
    if not start_match:
        return None
    end_match = re.search(r"\\end\{proof\}", region[start_match.end():])
    if not end_match:
        return None
    start_position = statement_end + start_match.start()
    end_position = statement_end + start_match.end() + end_match.end()
    return {
        "status": "located",
        "kind": "own_proof",
        "form": "proof_environment",
        "start_line": line_number(text, start_position),
        "end_line": line_number(text, end_position),
        "associated_label": label,
        "basis": "A complete proof environment follows this result before the next formal statement.",
    }


def support_locator(
    text: str,
    statement_start: int,
    statement_end: int,
    next_statement: int,
    label: str,
) -> dict:
    override = SUPPORT_OVERRIDES.get(label)
    if override:
        return {
            "status": "located",
            "associated_label": label,
            "form": "not_applicable",
            **override,
        }
    named = _named_proof(text, label)
    if named:
        return named
    adjacent = _adjacent_proof_environment(text, statement_end, next_statement, label)
    if adjacent:
        return adjacent
    return {
        "status": "pending",
        "kind": "support_pending",
        "form": "not_applicable",
        "start_line": None,
        "end_line": None,
        "associated_label": label,
        "basis": (
            "No exact own-proof heading or adjacent proof environment was located automatically. "
            "A later citation is not treated as proof."
        ),
    }


def parse_formal_results(text: str, units: list[dict]) -> list[dict]:
    pattern = re.compile(
        rf"\\begin\{{({FORMAL})\}}(?:\[([^\]]*)\])?"
        rf"(?:(?!\\end\{{\1\}}).)*?\\label\{{([^}}]+)\}}"
        rf"(?:(?!\\end\{{\1\}}).)*?\\end\{{\1\}}",
        re.S,
    )
    matches = list(pattern.finditer(text))
    results: list[dict] = []
    for index, match in enumerate(matches):
        label = match.group(3)
        unit = unit_for(match.start(), units)
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        statement_start_line = line_number(text, match.start())
        statement_end_line = line_number(text, match.end())
        support = support_locator(text, match.start(), match.end(), next_start, label)
        computational = None
        if label in P3_BY_LABEL:
            computational = {
                "status": "finite_computational_check",
                "oracle_group": P3_BY_LABEL[label],
                "scope": "finite complement; not a general proof",
            }
        statement_text = match.group(0)
        dependencies = sorted(set(
            dependency
            for dependency in re.findall(r"\\(?:eq)?ref\{([^}]+)\}", statement_text)
            if dependency != label
        ))
        results.append({
            "id": f"formal_{index + 1:03d}",
            "unit_id": unit["id"],
            "environment": match.group(1),
            "title": clean_title(match.group(2) or "Untitled formal result"),
            "latex_label": label,
            "statement_line": statement_start_line,
            "statement_locator": {
                "start_line": statement_start_line,
                "end_line": statement_end_line,
            },
            "hypotheses": {
                "status": "located_in_formal_statement",
                "kind": "formal_statement_conditions",
                "start_line": statement_start_line,
                "end_line": statement_end_line,
                "scope": "Conditions stated in the formal environment; upstream definitions remain linked through dependencies.",
            },
            "dependencies": [
                {"latex_label": dependency, "kind": "statement_cross_reference"}
                for dependency in dependencies
            ],
            "analytical_support": support,
            "support_class": (
                "finite_computational_check" if computational
                else ("analytical_support_located" if support["status"] == "located" else "support_pending")
            ),
            "computational_support": computational or {
                "status": "not_implemented_for_this_result",
                "scope": "analytical result; no numerical simulation is attributed",
            },
        })
    return results


def build_registry(manuscript: Path) -> dict:
    text = manuscript.read_text(encoding="utf-8")
    positional_units = parse_units(text)
    units = [{key: value for key, value in unit.items() if key != "source_position"} for unit in positional_units]
    results = parse_formal_results(text, positional_units)
    pending_units = {item["unit_id"] for item in results if item["analytical_support"]["status"] == "pending"}
    for unit in units:
        if unit["id"] in pending_units and "support_pending" not in unit["coverage_classes"]:
            unit["coverage_classes"].append("support_pending")
    return {
        "schema_version": 2,
        "manuscript_version": "v22",
        "manuscript_sha256": sha256(manuscript),
        "source_filename": manuscript.name,
        "scope_note": (
            "A located analytical support is a source locator, not an independent re-derivation. "
            "A pending support is disclosed rather than inferred from a citation. Finite computational "
            "checks do not prove the parent equilibrium. The reduced example is the only reproduced "
            "numerical application."
        ),
        "validation_contract": {
            "structural": "Runs without the manuscript and validates schema, classifications and locator structure.",
            "manuscript_backed": "Requires the identified v22 and validates its hash, formal labels, ranges, dependencies and proof associations.",
        },
        "allowed_classes": [
            "analytical_support_located", "support_pending", "finite_computational_check",
            "reproduced_numeric_result", "conceptual_explanation", "unimplemented_module",
        ],
        "units": units,
        "computational_links": [
            {"unit_id":"chapter_07","object":"direct-demand incidence","files":["RUN_DIR/results/scenarios.csv"],"scope":"reduced first-round slice; no NK equilibrium-output simulation"},
            {"unit_id":"chapter_10","object":"gross capture and net public resources","files":["RUN_DIR/results/scenarios.csv","RUN_DIR/results/cash_ledger.csv"],"scope":"synthetic fiscal instrument only"},
            {"unit_id":"chapter_11","object":"capacity conversion parameter","files":["RUN_DIR/results/scenarios.csv","RUN_DIR/results/sensitivity.csv"],"scope":"reduced capacity law; no estimated state process"},
            {"unit_id":"chapter_12","object":"future service and opportunity gate","files":["RUN_DIR/results/scenarios.csv","RUN_DIR/results/analytical_conditions.csv"],"scope":"single synthetic opportunity service"},
            {"unit_id":"chapter_16","object":"two gates and finite feasibility checks","files":["RUN_DIR/independent/oracle_results.json","RUN_DIR/results/conditional_gate_regions.csv"],"scope":"three finite complements; no viability kernel"},
            {"unit_id":"appendix_A","object":"worked reduced economy A-E","files":["RUN_DIR/results/scenarios.csv","RUN_DIR/results/constructive_case.csv","RUN_DIR/results/optimization_summary.csv"],"scope":"reproduced numerical result"}
        ],
        "formal_results": results,
    }


def markdown(registry: dict) -> str:
    result_counts: dict[str, int] = {}
    for result in registry["formal_results"]:
        result_counts[result["unit_id"]] = result_counts.get(result["unit_id"], 0) + 1
    lines = [
        "# Coverage by chapter and appendix", "",
        f"Manuscript: v22 (`{registry['manuscript_sha256']}`).", "",
        "This register separates own proofs, arguments inside statements, adjacent derivations and support still pending location. A locator is not an independent proof audit. The package does not simulate the complete HANK-New Keynesian parent model.", "",
        "The distributed structural check does not require the manuscript. A manuscript-backed check additionally validates the identified v22 hash, labels and source ranges.", "",
        "## Unit-level coverage", "",
        "| Unit | Title | Coverage classification | Formal results |", "|---|---|---|---:|",
    ]
    for unit in registry["units"]:
        lines.append(
            f"| {unit['id']} | {unit['title']} | {', '.join(unit['coverage_classes'])} | {result_counts.get(unit['id'], 0)} |"
        )
    lines.extend(["", "## Computational links", "", "| Unit | Object | Files | Scope |", "|---|---|---|---|"])
    for link in registry["computational_links"]:
        lines.append(f"| {link['unit_id']} | {link['object']} | {', '.join(link['files'])} | {link['scope']} |")
    lines.extend(["", "## Formal-result locators", "", "| Unit | Environment | Label | Statement | Hypotheses | Analytical support | Computational status |", "|---|---|---|---:|---|---|---|"])
    for result in registry["formal_results"]:
        statement = result["statement_locator"]
        support = result["analytical_support"]
        if support["status"] == "located":
            locator = f"{support['kind']} at lines {support['start_line']}-{support['end_line']}"
        else:
            locator = "support_pending"
        lines.append(
            f"| {result['unit_id']} | {result['environment']} | `{result['latex_label']}` | "
            f"{statement['start_line']}-{statement['end_line']} | formal statement | {locator} | "
            f"{result['computational_support']['status']} |"
        )
    lines.extend(["", "## Interpretation", "", "The registry says where a result is stated, where its declared analytical support is located when identified, and whether a finite calculation accompanies it. A later citation is not a proof. `support_pending` records that no qualifying support locator was established by this finite audit. The register does not certify every proof, estimate empirical parameters, or establish that the parent architecture is jointly computable.", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manuscript", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    manuscript = args.manuscript.resolve()
    registry = build_registry(manuscript)
    issues = validate_registry_data(registry, manuscript)
    if issues:
        raise ValueError(f"Generated coverage registry failed manuscript-backed validation: {issues}")
    args.registry.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown.write_text(markdown(registry), encoding="utf-8")
    print(json.dumps({
        "status": "passed",
        "validation_mode": "manuscript_backed",
        "units": len(registry["units"]),
        "formal_results": len(registry["formal_results"]),
        "support_located": sum(item["analytical_support"]["status"] == "located" for item in registry["formal_results"]),
        "support_pending": sum(item["analytical_support"]["status"] == "pending" for item in registry["formal_results"]),
        "registry": str(args.registry.resolve()),
        "markdown": str(args.markdown.resolve()),
    }, indent=2))


if __name__ == "__main__":
    main()
