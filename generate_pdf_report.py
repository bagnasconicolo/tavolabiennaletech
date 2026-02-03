#!/usr/bin/env python3
"""
Generate a LaTeX (PDF) report of samples by element, ordered by atomic number.

Data source:
- Google Apps Script JSON endpoint (same schema used by v3.py), or
- Optional CSV (custom mapping via command-line options).

Defaults to the Apps Script endpoint used by run.sh if provided.
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    # Reuse the data fetcher and periodic table metadata already in this repo.
    from v3 import PERIODIC_TABLE, fetch_sheet_data  # type: ignore
except Exception as exc:  # pragma: no cover
    raise SystemExit(
        "Failed to import PERIODIC_TABLE/fetch_sheet_data from v3.py. "
        "Make sure v3.py is present in the repo."
    ) from exc


@dataclass
class Sample:
    label: str
    state: str
    value: str


@dataclass
class ElementEntry:
    z: int
    symbol: str
    name: str
    samples: List[Sample]


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\\textbackslash{}",
        "&": r"\\&",
        "%": r"\\%",
        "$": r"\\$",
        "#": r"\\#",
        "_": r"\\_",
        "{": r"\\{",
        "}": r"\\}",
        "~": r"\\textasciitilde{}",
        "^": r"\\textasciicircum{}",
    }
    out = ""
    for ch in value:
        out += replacements.get(ch, ch)
    return out


def normalize_text(value: Optional[Any]) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def build_elements_from_api(data: Dict[str, Any]) -> List[ElementEntry]:
    elements_raw = data.get("elements", [])
    samples_by_symbol: Dict[str, List[Sample]] = {}

    for entry in elements_raw:
        symbol = normalize_text(entry.get("symbol"))
        samples: List[Sample] = []
        for idx, sample in enumerate(entry.get("samples", []), start=1):
            samples.append(
                Sample(
                    label=f"Campione {idx}",
                    state=normalize_text(sample.get("state")),
                    value=normalize_text(sample.get("value")),
                )
            )
        if symbol:
            samples_by_symbol[symbol] = samples

    elements: List[ElementEntry] = []
    for item in PERIODIC_TABLE:
        symbol = item["symbol"]
        samples = samples_by_symbol.get(symbol, [])
        if not samples:
            samples = [Sample(label=f"Campione {i}", state="", value="") for i in range(1, 5)]
        elements.append(
            ElementEntry(
                z=item["z"],
                symbol=symbol,
                name=item["name"],
                samples=samples,
            )
        )
    return elements


def build_elements_from_csv(path: Path, symbol_col: str, name_col: str) -> List[ElementEntry]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    rows: List[Dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append({k: (v or "").strip() for k, v in row.items()})

    rows_by_symbol = {row.get(symbol_col, "").strip(): row for row in rows}

    elements: List[ElementEntry] = []
    for item in PERIODIC_TABLE:
        symbol = item["symbol"]
        row = rows_by_symbol.get(symbol, {})
        name = row.get(name_col, "") or item["name"]
        samples: List[Sample] = []
        for idx in range(1, 5):
            state = row.get(f"state_{idx}", "")
            value = row.get(f"sample_{idx}", "")
            samples.append(Sample(label=f"Campione {idx}", state=state, value=value))
        elements.append(
            ElementEntry(
                z=item["z"],
                symbol=symbol,
                name=name,
                samples=samples,
            )
        )
    return elements


def render_latex(title: str, subtitle: str, elements: Iterable[ElementEntry]) -> str:
    today = date.today().strftime("%Y-%m-%d")
    header = r"""
\documentclass[10pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[margin=1.2cm]{geometry}
\usepackage{multicol}
\usepackage{tabularx}
\usepackage{array}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{enumitem}
\setlist{leftmargin=*,nosep}
\setlength{\columnsep}{0.8cm}
\setlength{\parindent}{0pt}
\setlength{\parskip}{3pt}
\renewcommand{\arraystretch}{1.1}
\pagestyle{fancy}
\fancyhf{}
\lhead{%(title)s}
\rhead{%(date)s}
\cfoot{\thepage}
\titleformat{\section}{\large\bfseries}{}{0pt}{}
""" % {
        "title": latex_escape(title),
        "date": latex_escape(today),
    }

    body_lines: List[str] = [
        header,
        r"\begin{document}",
        r"\begin{center}",
        rf"{{\LARGE\textbf{{{latex_escape(title)}}}}}\\",
        rf"{{\normalsize {latex_escape(subtitle)}}}\\",
        r"\end{center}",
        r"\vspace{0.4em}",
        r"\begin{multicols}{2}",
    ]

    for element in elements:
        label = f"{element.z} {element.symbol} — {element.name}"
        body_lines.append(r"\begin{samepage}")
        body_lines.append(rf"\textbf{{{latex_escape(label)}}}\\")
        body_lines.append(r"\begin{tabularx}{\linewidth}{@{}X@{}}")
        for sample in element.samples:
            state = sample.state or "-"
            value = sample.value or "-"
            details = f"{value} - {state}"
            body_lines.append(rf"{latex_escape(details)} \\")
        body_lines.append(r"\end{tabularx}")
        body_lines.append(r"\vspace{0.2em}")
        body_lines.append(r"\end{samepage}")

    body_lines.extend([
        r"\end{multicols}",
        r"\end{document}",
    ])

    return "\n".join(body_lines)


def run_pdflatex(tex_path: Path, output_dir: Path) -> None:
    command = [
        "pdflatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={output_dir}",
        str(tex_path),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except FileNotFoundError as exc:
        raise SystemExit(
            "pdflatex not found. Install a LaTeX distribution (e.g. MacTeX) "
            "and try again."
        ) from exc
    except subprocess.CalledProcessError as exc:
        output = exc.stdout.decode("utf-8", errors="ignore") if exc.stdout else ""
        raise SystemExit(f"pdflatex failed. Output:\n{output}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a LaTeX/PDF report of samples ordered by atomic number."
    )
    parser.add_argument("--api-url", help="Apps Script web app endpoint (ending with /exec)")
    parser.add_argument("--id", dest="sheet_id", default=None, help="Spreadsheet ID")
    parser.add_argument("--csv", type=Path, help="Optional CSV source instead of API")
    parser.add_argument("--csv-symbol", default="symbol", help="CSV column for element symbol")
    parser.add_argument("--csv-name", default="name", help="CSV column for element name")
    parser.add_argument("--title", default="Report campioni per elemento")
    parser.add_argument(
        "--subtitle",
        default="Piccolo Museo della Tavola Periodica @ Biennale Tech 2026",
    )
    parser.add_argument(
        "--output",
        default="output/elementi_report.pdf",
        help="Path for the generated PDF",
    )
    parser.add_argument(
        "--keep-tex",
        action="store_true",
        help="Keep the generated .tex file next to the PDF",
    )
    args = parser.parse_args()

    if not args.api_url and not args.csv:
        raise SystemExit("Provide --api-url or --csv for the data source.")

    if args.csv:
        elements = build_elements_from_csv(args.csv, args.csv_symbol, args.csv_name)
    else:
        data = fetch_sheet_data(args.api_url, args.sheet_id)
        elements = build_elements_from_api(data)

    elements.sort(key=lambda item: item.z)

    output_pdf = Path(args.output)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    tex_path = output_pdf.with_suffix(".tex")

    latex_source = render_latex(args.title, args.subtitle, elements)
    tex_path.write_text(latex_source, encoding="utf-8")

    run_pdflatex(tex_path, output_pdf.parent)

    generated_pdf = output_pdf.parent / tex_path.with_suffix(".pdf").name
    if generated_pdf != output_pdf:
        generated_pdf.replace(output_pdf)

    if not args.keep_tex:
        try:
            tex_path.unlink()
        except OSError:
            pass

    print(f"Generated {output_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
