"""P4 editorial assets derived from a verified reproduction run."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import reportlab
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .verification import verify_run


INK = HexColor("#262C36")
BLUE = HexColor("#315A93")
ORANGE = HexColor("#BD6515")
PALE_BLUE = HexColor("#E0EDFA")
PALE_GREEN = HexColor("#E5F2D6")
PALE_GRAY = HexColor("#F0F0F0")
PALE_ORANGE = HexColor("#FAE8D6")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().lower()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required run output is missing: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _row(rows: list[dict[str, str]], key: str, value: str) -> dict[str, str]:
    matches = [row for row in rows if row.get(key) == value]
    if len(matches) != 1:
        raise ValueError(f"Expected one row where {key}={value!r}; observed {len(matches)}.")
    return matches[0]


def _number(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite editorial input: {value!r}")
    return result


def _boolean(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"Expected serialized boolean, observed {value!r}.")


def _escape_tex(value: str) -> str:
    replacements = {
        "&": r"\&", "%": r"\%", "_": r"\_", "#": r"\#",
    }
    return "".join(replacements.get(character, character) for character in value)


def _font_contract(package_root: Path) -> dict[str, Any]:
    fonts = Path(reportlab.__file__).resolve().parent / "fonts"
    files = {
        "normal": fonts / "Vera.ttf",
        "bold": fonts / "VeraBd.ttf",
        "italic": fonts / "VeraIt.ttf",
        "bold_italic": fonts / "VeraBI.ttf",
    }
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"ReportLab Bitstream Vera fonts are missing: {missing}")
    license_path = package_root / "assets" / "fonts" / "BITSTREAM_VERA_LICENSE.txt"
    if not license_path.is_file():
        raise FileNotFoundError(f"Bundled font license notice is missing: {license_path}")
    names = {
        "normal": "BookFigureVera",
        "bold": "BookFigureVeraBold",
        "italic": "BookFigureVeraItalic",
        "bold_italic": "BookFigureVeraBoldItalic",
    }
    for role, path in files.items():
        if names[role] not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(names[role], str(path)))
    pdfmetrics.registerFontFamily(
        "BookFigureVera",
        normal=names["normal"],
        bold=names["bold"],
        italic=names["italic"],
        boldItalic=names["bold_italic"],
    )
    return {
        "family": "Bitstream Vera Sans",
        "reportlab_version": reportlab.Version,
        "source": "fonts bundled with the pinned ReportLab dependency",
        "license": "Bitstream Vera Fonts Copyright",
        "license_path": str(license_path),
        "license_sha256": sha256(license_path),
        "files": {role: {"path": str(path), "sha256": sha256(path)} for role, path in files.items()},
        "registered_names": names,
    }


def _text(pdf: canvas.Canvas, x: float, y: float, value: str, size: float = 11,
          bold: bool = False, align: str = "left") -> None:
    pdf.setFillColor(INK)
    pdf.setFont("BookFigureVeraBold" if bold else "BookFigureVera", size)
    method = {"left": pdf.drawString, "center": pdf.drawCentredString, "right": pdf.drawRightString}[align]
    method(x, y, value)


def _axes(pdf: canvas.Canvas, x0: float, y0: float, width: float, height: float,
          xmin: float, xmax: float, ymin: float, ymax: float,
          xticks: list[float], yticks: list[float], xlabel: str, ylabel: str):
    sx = lambda value: x0 + (float(value) - xmin) * width / (xmax - xmin)
    sy = lambda value: y0 + (float(value) - ymin) * height / (ymax - ymin)
    pdf.setLineWidth(0.7)
    pdf.setStrokeColor(INK)
    pdf.rect(x0, y0, width, height, fill=0, stroke=1)
    for value in xticks:
        pdf.line(sx(value), y0, sx(value), y0 - 4)
        _text(pdf, sx(value), y0 - 18, f"{value:g}", 9, align="center")
    for value in yticks:
        pdf.line(x0 - 4, sy(value), x0, sy(value))
        _text(pdf, x0 - 8, sy(value) - 3, f"{value:g}", 9, align="right")
    _text(pdf, x0 + width / 2, y0 - 39, xlabel, 10, align="center")
    pdf.saveState()
    pdf.translate(x0 - 53, y0 + height / 2)
    pdf.rotate(90)
    _text(pdf, 0, 0, ylabel, 10, align="center")
    pdf.restoreState()
    return sx, sy


def _point(pdf: canvas.Canvas, x: float, y: float, label: str, color) -> None:
    pdf.setFillColor(color)
    pdf.setStrokeColor(INK)
    pdf.circle(x, y, 5.3, stroke=1, fill=1)
    _text(pdf, x + 8, y + 4, label, 11, bold=True)


def _scenario_figure(run: Path, output: Path, font: dict[str, Any]) -> dict[str, Any]:
    scenarios = _read_csv(run / "results" / "scenarios.csv")
    parameters = _read_csv(run / "results" / "parameters.csv")
    opportunity_min = _number(_row(parameters, "symbol", "O_min")["value"])
    coordinates = [
        {
            "scenario": row["scenario"],
            "direct_demand_margin": _number(row["delta_D0_dir"]),
            "opportunity_margin": _number(row["O_1"]) - opportunity_min,
            "direct_demand_unit": "date-0 goods at P0=P1=1",
            "opportunity_unit": "opportunity index minus target",
        }
        for row in scenarios
    ]
    xs = [row["direct_demand_margin"] for row in coordinates]
    ys = [row["opportunity_margin"] for row in coordinates]
    xmin, xmax = math.floor(min(xs)) - 1, math.ceil(max(xs))
    ymin, ymax = math.floor(min(ys)) - 1, math.ceil(max(ys)) + 1
    pdf = canvas.Canvas(str(output), pagesize=(500, 360), initialFontName="BookFigureVera", pageCompression=1)
    pdf.setAuthor("Vicenzo Scavino Alfaro")
    pdf.setTitle("Cases A-D in the two-gate plane")
    sx, sy = _axes(
        pdf, 75, 58, 365, 235, xmin, xmax, ymin, ymax,
        [-12, -9, -6, -3, 0], [-4, -3, -2, -1, 0, 1],
        "Change in direct demand (date-0 goods)",
        "Opportunity above the target (index units)",
    )
    _text(pdf, 75, 332, "Cases A-D in the two-gate plane", 12, bold=True)
    _text(pdf, 75, 313, "Each gate passes at a margin of zero or above.", 9)
    pdf.setLineWidth(1)
    pdf.line(sx(0), 58, sx(0), 293)
    pdf.line(75, sy(0), 440, sy(0))
    for row in coordinates:
        _point(
            pdf, sx(row["direct_demand_margin"]), sy(row["opportunity_margin"]),
            row["scenario"], ORANGE if row["direct_demand_margin"] >= 0 else BLUE,
        )
    pdf.showPage()
    pdf.save()
    return {
        "file": output.name,
        "sources": ["results/scenarios.csv", "results/parameters.csv:O_min"],
        "transformation": "y = O_1 - O_min; x = delta_D0_dir",
        "coordinates": coordinates,
        "axis_domain": {"x": [xmin, xmax], "y": [ymin, ymax]},
        "labels": {
            "title": "Cases A-D in the two-gate plane",
            "x": "Change in direct demand (date-0 goods)",
            "y": "Opportunity above the target (index units)",
        },
        "font_family": font["family"],
        "sha256": sha256(output),
    }


def _fraction_evidence(run: Path) -> tuple[str, str]:
    oracle = json.loads((run / "independent" / "oracle_results.json").read_text(encoding="utf-8"))
    group = next(item for item in oracle["checks"] if item["id"] == "A05_exact_frontiers_and_inclusive_boundaries")
    return group["evidence"]["m_H_star"], group["evidence"]["phi_star"]


def _conditional_figure(run: Path, output: Path, font: dict[str, Any]) -> dict[str, Any]:
    threshold_row = _read_csv(run / "results" / "fixed_policy_gate_thresholds.csv")[0]
    m_star = _number(threshold_row["demand_m_h_max"])
    phi_star = _number(threshold_row["opportunity_phi_min"])
    m_exact, phi_exact = _fraction_evidence(run)
    grid = _read_csv(run / "results" / "conditional_gate_regions.csv")
    mismatches = []
    for index, row in enumerate(grid, start=2):
        expected_demand = _number(row["m_H"]) <= m_star + 1.0e-12
        expected_opportunity = _number(row["phi"]) >= phi_star - 1.0e-12
        if _boolean(row["demand_gate"]) != expected_demand or _boolean(row["opportunity_gate"]) != expected_opportunity:
            mismatches.append(index)
    if mismatches:
        raise AssertionError(f"Conditional-region rows disagree with exact frontiers: {mismatches[:10]}")
    parameters = _read_csv(run / "results" / "parameters.csv")
    scenarios = _read_csv(run / "results" / "scenarios.csv")
    constructive = _read_csv(run / "results" / "constructive_case.csv")[0]
    benchmark_m = _number(_row(parameters, "symbol", "m_H=m_T")["value"])
    points = []
    for name in ("C", "D"):
        row = _row(scenarios, "scenario", name)
        points.append({"scenario": name, "m_H": benchmark_m, "phi": _number(row["phi"])})
    points.append({"scenario": "E", "m_H": _number(constructive["m_H"]), "phi": _number(constructive["phi"])})
    xs = sorted({_number(row["m_H"]) for row in grid})
    ys = sorted({_number(row["phi"]) for row in grid})
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    pdf = canvas.Canvas(str(output), pagesize=(620, 410), initialFontName="BookFigureVera", pageCompression=1)
    pdf.setAuthor("Vicenzo Scavino Alfaro")
    pdf.setTitle("Conditional regions for the fixed Case C allocation")
    x0, y0, width, height = 82, 60, 470, 285
    sx0 = lambda value: x0 + (float(value) - xmin) * width / (xmax - xmin)
    sy0 = lambda value: y0 + (float(value) - ymin) * height / (ymax - ymin)
    x_star, y_star = sx0(m_star), sy0(phi_star)
    for x, y, w, h, color in (
        (x0, y0, x_star - x0, y_star - y0, PALE_BLUE),
        (x0, y_star, x_star - x0, y0 + height - y_star, PALE_GREEN),
        (x_star, y0, x0 + width - x_star, y_star - y0, PALE_GRAY),
        (x_star, y_star, x0 + width - x_star, y0 + height - y_star, PALE_ORANGE),
    ):
        pdf.setFillColor(color)
        pdf.rect(x, y, w, h, stroke=0, fill=1)
    sx, sy = _axes(
        pdf, x0, y0, width, height, xmin, xmax, ymin, ymax,
        [0.35, 0.50, 0.65, 0.80, 0.95], [0.05, 0.10, 0.20, 0.25, 0.30, 0.35],
        "Spending response of exposed households",
        "Capacity conversion per investment unit",
    )
    _text(pdf, x0, 374, "Conditional regions for the fixed Case C allocation", 11, bold=True)
    pdf.setStrokeColor(INK)
    pdf.setDash(5, 3)
    pdf.setLineWidth(1)
    pdf.line(x_star, y0, x_star, y0 + height)
    pdf.line(x0, y_star, x0 + width, y_star)
    pdf.setDash()
    labels = (
        ((x0 + x_star) / 2, (y0 + y_star) / 2, "Demand only"),
        ((x0 + x_star) / 2, (y_star + y0 + height) / 2, "Both pass"),
        ((x_star + x0 + width) / 2, (y0 + y_star) / 2, "Neither"),
        ((x_star + x0 + width) / 2, (y_star + y0 + height) / 2, "Opportunity only"),
    )
    for x, y, label in labels:
        _text(pdf, x, y, label, 10, bold=True, align="center")
    _text(pdf, x_star + 5, y0 + 7, f"m_H* = {m_exact}", 9)
    _text(pdf, x0 + 5, y_star + 5, f"phi* = {phi_exact}", 9)
    for point in points:
        _point(pdf, sx(point["m_H"]), sy(point["phi"]), point["scenario"], ORANGE if point["scenario"] == "E" else BLUE)
    pdf.showPage()
    pdf.save()
    return {
        "file": output.name,
        "sources": [
            "results/conditional_gate_regions.csv",
            "results/fixed_policy_gate_thresholds.csv",
            "results/scenarios.csv",
            "results/constructive_case.csv",
            "independent/oracle_results.json:A05",
        ],
        "grid_rows_checked": len(grid),
        "grid_frontier_mismatches": 0,
        "boundaries": {"m_H_decimal": m_star, "m_H_exact": m_exact, "phi_decimal": phi_star, "phi_exact": phi_exact},
        "points": points,
        "axis_domain": {"m_H": [xmin, xmax], "phi": [ymin, ymax]},
        "labels": {
            "title": "Conditional regions for the fixed Case C allocation",
            "x": "Spending response of exposed households",
            "y": "Capacity conversion per investment unit",
        },
        "font_family": font["family"],
        "sha256": sha256(output),
    }


def _write_tables(run: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    benchmark_path = run / "inputs" / "config" / "benchmark.json"
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    benchmark_parameters = benchmark["parameters"]
    parameters = _read_csv(run / "results" / "parameters.csv")
    scenarios = _read_csv(run / "results" / "scenarios.csv")
    constructive = _read_csv(run / "results" / "constructive_case.csv")[0]
    analytical = _read_csv(run / "results" / "analytical_conditions.csv")
    optimization = _read_csv(run / "results" / "optimization_summary.csv")
    checks = _read_csv(run / "results" / "accounting_checks.csv")
    constructive_checks = _read_csv(run / "results" / "constructive_case_accounting_checks.csv")
    m_h = _number(_row(parameters, "symbol", "m_H=m_T")["value"])

    income_h_0 = _number(benchmark_parameters["income_h_0"])
    income_s_0 = _number(benchmark_parameters["income_s_0"])
    consumption_h_0 = _number(benchmark_parameters["consumption_h_0"])
    consumption_s_0 = _number(benchmark_parameters["consumption_s_0"])
    saving_h_0 = income_h_0 - consumption_h_0
    saving_s_0 = income_s_0 - consumption_s_0
    household_closure = "\n".join((
        r"\begin{gathered}",
        f"d_{{\\mathrm{{adm}}}}={_number(benchmark_parameters['d_admin']):g},\\quad "
        f"d_I={_number(benchmark_parameters['d_investment']):g},\\quad "
        f"C_{{H0}}={consumption_h_0:g},\\quad C_{{S0}}={consumption_s_0:g},\\\\",
        r"S_{j0}=Y_{j0}-C_{j0}\quad (j\in\{H,S\}),\\",
        f"(S_{{H0}},S_{{S0}})=({saving_h_0:g},{saving_s_0:g}).",
        r"\end{gathered}",
    )) + "\n"
    (output / "household_closure.tex").write_text(household_closure, encoding="utf-8")

    parameter_lines = [
        r"\begin{longtable}{@{}p{0.17\textwidth}rp{0.22\textwidth}p{0.42\textwidth}@{}}",
        r"\caption{Synthetic parameters and units}\label{tab:synthetic-parameters}\\",
        r"\toprule Symbol & Value & Unit & Interpretation \\", r"\midrule", r"\endhead",
    ]
    for row in parameters:
        parameter_lines.append(
            f"\\texttt{{{_escape_tex(row['symbol'])}}} & {_number(row['value']):.3f} & "
            f"{_escape_tex(row['unit'])} & {_escape_tex(row['interpretation'])} \\\\"
        )
    parameter_lines.extend([r"\bottomrule", r"\end{longtable}"])
    (output / "parameters_table.tex").write_text("\n".join(parameter_lines) + "\n", encoding="utf-8")

    all_cases = [dict(row) for row in scenarios] + [dict(constructive)]
    case_lines = [
        r"\begin{tabular}{@{}lrrrrrrrrll@{}}", r"\toprule",
        r"Case & $m_H$ & $\phi$ & $T$ & $y_T$ & $I_q$ & $B_0=X_1$ & $\Delta D_0^{dir}$ & $O_1$ & Demand & Opportunity \\",
        r"\midrule",
    ]
    for row in all_cases:
        row_m_h = _number(row["m_H"]) if row["scenario"] == "E" else m_h
        case_lines.append(
            f"{row['scenario']} & {row_m_h:.2f} & {_number(row['phi']):.2f} & {_number(row['T']):g} & "
            f"{_number(row['y_T']):g} & {_number(row['I_q']):g} & {_number(row['B_0']):g} & "
            f"{_number(row['delta_D0_dir']):.1f} & {_number(row['O_1']):.2f} & "
            f"{'pass' if _boolean(row['demand_gate']) else 'fail'} & {'pass' if _boolean(row['opportunity_gate']) else 'fail'} \\\\"
        )
    case_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (output / "cases_table.tex").write_text("\n".join(case_lines) + "\n", encoding="utf-8")

    analytical_lines = [
        r"\begin{tabular}{@{}llrrrrrl@{}}", r"\toprule",
        r"Capacity & Transfer & $\phi$ & $X_{min}$ & $I_{min}$ & $B_{min}$ & Total finance & Feasible \\",
        r"\midrule",
    ]
    for row in analytical:
        analytical_lines.append(
            f"{row['capacity_case'].title()} & {_number(row['fixed_transfer']):g} & {_number(row['phi']):.3f} & "
            f"{_number(row['X_min']):.3f} & {_number(row['I_min']):.3f} & {_number(row['B_min']):.3f} & "
            f"{_number(row['minimum_date0_finance']):.3f} & {'yes' if _boolean(row['fiscally_feasible']) else 'no'} \\\\"
        )
    analytical_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (output / "analytical_table.tex").write_text("\n".join(analytical_lines) + "\n", encoding="utf-8")

    optimization_lines = [
        r"\begin{tabular}{@{}lrrrrl@{}}", r"\toprule",
        r"Problem & Maximum $\Delta D_0^{dir}$ & $I_q$ & $y_T$ & $B_0$ & Opportunity financed \\",
        r"\midrule",
    ]
    for row in optimization:
        label = "Productive ceiling" if row["case"] == "productive_investment_ceiling" else "Ceiling removed"
        optimization_lines.append(
            f"{label} & {_number(row['delta_demand_max']):.3f} & {_number(row['investment']):.3f} & "
            f"{_number(row['transfer']):.3f} & {_number(row['reserve']):.3f} & "
            f"{'yes' if _boolean(row['opportunity_floor_financed']) else 'no'} \\\\"
        )
    optimization_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (output / "optimization_table.tex").write_text("\n".join(optimization_lines) + "\n", encoding="utf-8")

    all_checks = checks + constructive_checks
    accounting_lines = [
        r"\begin{tabular}{@{}lrrl@{}}", r"\toprule",
        r"Case & Checks & Maximum absolute residual & Status \\", r"\midrule",
    ]
    for scenario in "ABCDE":
        subset = [row for row in all_checks if row["scenario"] == scenario]
        maximum = max(abs(_number(row["residual"])) for row in subset)
        status = "PASS" if all(row["status"] == "PASS" for row in subset) else "FAIL"
        accounting_lines.append(f"{scenario} & {len(subset)} & {maximum:.2e} & {status} \\\\ ")
    accounting_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (output / "accounting_table.tex").write_text("\n".join(accounting_lines) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "status": "passed",
        "rule": "Displayed results are formatted from unrounded CSV fields; baseline closure values are derived from the verified run configuration.",
        "sources": {
            **{
                name: sha256(run / "results" / name)
                for name in (
                    "parameters.csv", "scenarios.csv", "constructive_case.csv",
                    "analytical_conditions.csv", "optimization_summary.csv",
                    "accounting_checks.csv", "constructive_case_accounting_checks.csv",
                )
            },
            "inputs/config/benchmark.json": sha256(benchmark_path),
        },
        "presentation": {
            "cases": {"m_H": 2, "phi": 2, "delta_D0_dir": 1, "O_1": 2},
            "analytical": 3,
            "optimization": 3,
            "accounting_residual": "scientific_2",
            "parameters": 3,
            "household_closure": "effective_run_configuration",
        },
        "outputs": {},
    }
    for path in sorted(output.glob("*.tex")):
        manifest["outputs"][path.name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    return manifest


def _compiler_version(executable: str) -> str:
    completed = subprocess.run([executable, "--version"], text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        return "unavailable"
    lines = [line.strip() for line in (completed.stdout + "\n" + completed.stderr).splitlines() if line.strip()]
    for pattern in (r"\bLatexmk\b.*\bVersion\b", r"\bpdfTeX\b.*\bTeX Live\b"):
        for line in lines:
            if re.search(pattern, line, flags=re.IGNORECASE):
                return line
    return lines[0] if lines else "unavailable"


def _pdf_page_count(path: Path) -> int:
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        raise RuntimeError("pdfinfo must be available on PATH to count the compiled document pages.")
    completed = subprocess.run([pdfinfo, str(path)], text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"pdfinfo failed with exit code {completed.returncode}: {completed.stderr.strip()}")
    match = re.search(r"^Pages:\s+(\d+)\s*$", completed.stdout, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("pdfinfo did not report a page count.")
    pages = int(match.group(1))
    if pages < 1:
        raise RuntimeError(f"pdfinfo reported an invalid page count: {pages}.")
    return pages


def build_docs(package_root: Path, run: Path, output: Path) -> dict[str, Any]:
    """Build the standalone document without modifying the sealed run."""
    package_root, run, output = package_root.resolve(), run.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError(f"Documentation output already exists: {output}")
    verification = verify_run(package_root, run)
    if verification["status"] != "passed":
        raise AssertionError("The source run did not pass completed-run verification.")
    if verification["run_identity"]["relation_to_current_package"] != "current":
        raise AssertionError("build-docs requires a run produced by the current package source tree.")
    start = time.perf_counter()
    output.mkdir(parents=True)
    tables = output / "tables"
    figures = output / "figures"
    figures.mkdir()
    table_manifest = _write_tables(run, tables)
    (output / "table_manifest.json").write_text(json.dumps(table_manifest, indent=2, sort_keys=True), encoding="utf-8")
    font = _font_contract(package_root)
    figure_records = [
        _scenario_figure(run, figures / "scenario_gate_map.pdf", font),
        _conditional_figure(run, figures / "conditional_gate_regions.pdf", font),
    ]
    figure_validation = {
        "schema_version": 1,
        "status": "passed",
        "font_contract": font,
        "figures": figure_records,
        "scientific_equivalence": {
            "status": "passed",
            "basis": "computed coordinates, transformations, exact boundaries, units and region classifications",
            "binary_pdf_identity_required": False,
            "typography_difference": "Bitstream Vera Sans replaces the locally installed Arial used by the v22 editorial figures.",
        },
        "visual_review": {"status": "pending_external_inspection", "pages_expected": 2},
    }
    (output / "figure_validation.json").write_text(json.dumps(figure_validation, indent=2, sort_keys=True), encoding="utf-8")
    template = package_root / "docs" / "example_EN.tex"
    shutil.copy2(template, output / "example_EN.tex")
    latexmk = shutil.which("latexmk")
    pdflatex = shutil.which("pdflatex")
    if not latexmk or not pdflatex:
        raise RuntimeError("latexmk and pdflatex must be available on PATH for build-docs.")
    command = [latexmk, "-pdf", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "example_EN.tex"]
    completed = subprocess.run(command, cwd=output, text=True, capture_output=True, check=False)
    (output / "latexmk.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output / "latexmk.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"LaTeX compilation failed with exit code {completed.returncode}.")
    pdf = output / "example_EN.pdf"
    log = (output / "example_EN.log").read_text(encoding="utf-8", errors="replace")
    overfull = len(re.findall(r"Overfull \\[hv]box", log))
    undefined = len(re.findall(r"undefined references|Citation .* undefined", log, flags=re.IGNORECASE))
    if overfull or undefined:
        raise AssertionError(f"Document log has overfull={overfull}, undefined={undefined}.")
    report = {
        "schema_version": 1,
        "status": "passed",
        "source_run": str(run),
        "source_run_report_sha256": sha256(run / "run_report.json"),
        "source_run_verification": {
            "status": verification["status"],
            "relation_to_current_package": verification["run_identity"]["relation_to_current_package"],
        },
        "command": command,
        "latexmk_version": _compiler_version(latexmk),
        "pdflatex_version": _compiler_version(pdflatex),
        "seconds": time.perf_counter() - start,
        "tables": table_manifest,
        "figures": figure_validation,
        "document": {
            "source": "example_EN.tex",
            "source_sha256": sha256(output / "example_EN.tex"),
            "pdf": "example_EN.pdf",
            "pdf_sha256": sha256(pdf),
            "pages": _pdf_page_count(pdf),
            "overfull_boxes": overfull,
            "undefined_references_or_citations": undefined,
            "visual_review": "pending_external_inspection",
        },
    }
    (output / "build_docs_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
