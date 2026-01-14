#!/usr/bin/env python3
"""
Generate an interactive periodic table HTML from a Google Sheets-backed sample
tracking spreadsheet.

This script fetches a JSON payload from a Google Apps Script web app.  The
Apps Script must expose an endpoint (via `doGet`) that reads the first sheet
of a spreadsheet whose rows correspond to the 118 chemical elements.  Each
row has the following structure:

  * Column A: The element symbol (e.g. "H", "He", "Li", ...).
  * Columns B–E: Four sample fields.  These cells may contain arbitrary
    values (for example, identifiers or comments) and are coloured
    according to a legend defined in cells G2:G6.  The legend cells
    contain the textual state (e.g. "da comprare", "in arrivo", …) and
    their background colours define the colour for that state.

The Apps Script should return a JSON object with the following structure:

```
{
  "elements": [
    {
      "row": <1–118>,
      "symbol": "H",
      "samples": [
        {"value": <original cell value>, "state": <legend label>, "color": <hex>},
        {"value": …},
        {"value": …},
        {"value": …}
      ]
    },
    …
  ],
  "legend": {"#ff0000": "da comprare", …},
  "labelColors": {"da comprare": "#ff0000", …}
}
```

The script maps each element to its position in the periodic table using a
built‑in lookup table containing atomic number, symbol, English name,
group (1–18) and period (1–7).  It then renders an HTML file where each
element appears in its appropriate cell.  Inside each cell, a 2×2 grid
indicates the four samples; each quarter cell is coloured according to the
sample's state.  Hovering over an element reveals a tooltip with the
symbol, English name, atomic number and per‑sample details (state and
value).  A legend illustrating the mapping from state to colour is also
included.

Usage:

  python generate_periodic_table_from_samples.py \
    --api-url "https://script.google.com/macros/s/<deployment>/exec" \
    --output periodic_table.html

Optional arguments:

  --id               Spreadsheet ID (if not hardcoded in the Apps Script)
  --title            Title for the HTML document
  --dump-json FILE   Save the raw JSON returned from the endpoint to FILE

Requirements:

  This script depends only on the `requests` library, which can be
  installed via pip if not already available:

      pip install requests

Author: OpenAI's ChatGPT
License: MIT
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "The 'requests' library is required to run this script.\n"
        "Install it with 'pip install requests' and try again."
    ) from exc


###############################################################################
# Periodic table metadata
#
# The following list contains one dictionary per element.  Each entry
# specifies the atomic number (`z`), element symbol (`symbol`), English name
# (`name`), group (1–18) and period (1–7).  Lanthanides (57–71) and
# actinides (89–103) are assigned group 3 and their natural period (6 and
# 7, respectively); during layout they are moved into the f‑block rows.
#
# This table is derived from the IUPAC periodic table (as of 2024) and is
# sufficient for positioning elements on a conventional 18×7 periodic table.
###############################################################################

PERIODIC_TABLE: List[Dict[str, Any]] = [
    # period 1
    {"z": 1, "symbol": "H",  "name": "Hydrogen",     "group": 1,  "period": 1},
    {"z": 2, "symbol": "He", "name": "Helium",       "group": 18, "period": 1},
    # period 2
    {"z": 3, "symbol": "Li", "name": "Lithium",       "group": 1,  "period": 2},
    {"z": 4, "symbol": "Be", "name": "Beryllium",     "group": 2,  "period": 2},
    {"z": 5, "symbol": "B",  "name": "Boron",         "group": 13, "period": 2},
    {"z": 6, "symbol": "C",  "name": "Carbon",        "group": 14, "period": 2},
    {"z": 7, "symbol": "N",  "name": "Nitrogen",      "group": 15, "period": 2},
    {"z": 8, "symbol": "O",  "name": "Oxygen",        "group": 16, "period": 2},
    {"z": 9, "symbol": "F",  "name": "Fluorine",      "group": 17, "period": 2},
    {"z": 10, "symbol": "Ne", "name": "Neon",         "group": 18, "period": 2},
    # period 3
    {"z": 11, "symbol": "Na", "name": "Sodium",        "group": 1,  "period": 3},
    {"z": 12, "symbol": "Mg", "name": "Magnesium",     "group": 2,  "period": 3},
    {"z": 13, "symbol": "Al", "name": "Aluminium",     "group": 13, "period": 3},
    {"z": 14, "symbol": "Si", "name": "Silicon",       "group": 14, "period": 3},
    {"z": 15, "symbol": "P",  "name": "Phosphorus",    "group": 15, "period": 3},
    {"z": 16, "symbol": "S",  "name": "Sulfur",        "group": 16, "period": 3},
    {"z": 17, "symbol": "Cl", "name": "Chlorine",      "group": 17, "period": 3},
    {"z": 18, "symbol": "Ar", "name": "Argon",         "group": 18, "period": 3},
    # period 4
    {"z": 19, "symbol": "K",  "name": "Potassium",     "group": 1,  "period": 4},
    {"z": 20, "symbol": "Ca", "name": "Calcium",       "group": 2,  "period": 4},
    {"z": 21, "symbol": "Sc", "name": "Scandium",      "group": 3,  "period": 4},
    {"z": 22, "symbol": "Ti", "name": "Titanium",      "group": 4,  "period": 4},
    {"z": 23, "symbol": "V",  "name": "Vanadium",      "group": 5,  "period": 4},
    {"z": 24, "symbol": "Cr", "name": "Chromium",      "group": 6,  "period": 4},
    {"z": 25, "symbol": "Mn", "name": "Manganese",     "group": 7,  "period": 4},
    {"z": 26, "symbol": "Fe", "name": "Iron",          "group": 8,  "period": 4},
    {"z": 27, "symbol": "Co", "name": "Cobalt",        "group": 9,  "period": 4},
    {"z": 28, "symbol": "Ni", "name": "Nickel",        "group": 10, "period": 4},
    {"z": 29, "symbol": "Cu", "name": "Copper",        "group": 11, "period": 4},
    {"z": 30, "symbol": "Zn", "name": "Zinc",          "group": 12, "period": 4},
    {"z": 31, "symbol": "Ga", "name": "Gallium",       "group": 13, "period": 4},
    {"z": 32, "symbol": "Ge", "name": "Germanium",     "group": 14, "period": 4},
    {"z": 33, "symbol": "As", "name": "Arsenic",       "group": 15, "period": 4},
    {"z": 34, "symbol": "Se", "name": "Selenium",      "group": 16, "period": 4},
    {"z": 35, "symbol": "Br", "name": "Bromine",       "group": 17, "period": 4},
    {"z": 36, "symbol": "Kr", "name": "Krypton",       "group": 18, "period": 4},
    # period 5
    {"z": 37, "symbol": "Rb", "name": "Rubidium",      "group": 1,  "period": 5},
    {"z": 38, "symbol": "Sr", "name": "Strontium",     "group": 2,  "period": 5},
    {"z": 39, "symbol": "Y",  "name": "Yttrium",       "group": 3,  "period": 5},
    {"z": 40, "symbol": "Zr", "name": "Zirconium",     "group": 4,  "period": 5},
    {"z": 41, "symbol": "Nb", "name": "Niobium",       "group": 5,  "period": 5},
    {"z": 42, "symbol": "Mo", "name": "Molybdenum",    "group": 6,  "period": 5},
    {"z": 43, "symbol": "Tc", "name": "Technetium",    "group": 7,  "period": 5},
    {"z": 44, "symbol": "Ru", "name": "Ruthenium",     "group": 8,  "period": 5},
    {"z": 45, "symbol": "Rh", "name": "Rhodium",       "group": 9,  "period": 5},
    {"z": 46, "symbol": "Pd", "name": "Palladium",     "group": 10, "period": 5},
    {"z": 47, "symbol": "Ag", "name": "Silver",        "group": 11, "period": 5},
    {"z": 48, "symbol": "Cd", "name": "Cadmium",       "group": 12, "period": 5},
    {"z": 49, "symbol": "In", "name": "Indium",        "group": 13, "period": 5},
    {"z": 50, "symbol": "Sn", "name": "Tin",           "group": 14, "period": 5},
    {"z": 51, "symbol": "Sb", "name": "Antimony",      "group": 15, "period": 5},
    {"z": 52, "symbol": "Te", "name": "Tellurium",     "group": 16, "period": 5},
    {"z": 53, "symbol": "I",  "name": "Iodine",        "group": 17, "period": 5},
    {"z": 54, "symbol": "Xe", "name": "Xenon",         "group": 18, "period": 5},
    # period 6 (includes lanthanides)
    {"z": 55, "symbol": "Cs", "name": "Caesium",       "group": 1,  "period": 6},
    {"z": 56, "symbol": "Ba", "name": "Barium",        "group": 2,  "period": 6},
    {"z": 57, "symbol": "La", "name": "Lanthanum",     "group": 3,  "period": 6},
    {"z": 58, "symbol": "Ce", "name": "Cerium",        "group": 3,  "period": 6},
    {"z": 59, "symbol": "Pr", "name": "Praseodymium",  "group": 3,  "period": 6},
    {"z": 60, "symbol": "Nd", "name": "Neodymium",     "group": 3,  "period": 6},
    {"z": 61, "symbol": "Pm", "name": "Promethium",   "group": 3,  "period": 6},
    {"z": 62, "symbol": "Sm", "name": "Samarium",      "group": 3,  "period": 6},
    {"z": 63, "symbol": "Eu", "name": "Europium",      "group": 3,  "period": 6},
    {"z": 64, "symbol": "Gd", "name": "Gadolinium",    "group": 3,  "period": 6},
    {"z": 65, "symbol": "Tb", "name": "Terbium",       "group": 3,  "period": 6},
    {"z": 66, "symbol": "Dy", "name": "Dysprosium",    "group": 3,  "period": 6},
    {"z": 67, "symbol": "Ho", "name": "Holmium",       "group": 3,  "period": 6},
    {"z": 68, "symbol": "Er", "name": "Erbium",        "group": 3,  "period": 6},
    {"z": 69, "symbol": "Tm", "name": "Thulium",       "group": 3,  "period": 6},
    {"z": 70, "symbol": "Yb", "name": "Ytterbium",     "group": 3,  "period": 6},
    {"z": 71, "symbol": "Lu", "name": "Lutetium",      "group": 3,  "period": 6},
    {"z": 72, "symbol": "Hf", "name": "Hafnium",       "group": 4,  "period": 6},
    {"z": 73, "symbol": "Ta", "name": "Tantalum",      "group": 5,  "period": 6},
    {"z": 74, "symbol": "W",  "name": "Tungsten",      "group": 6,  "period": 6},
    {"z": 75, "symbol": "Re", "name": "Rhenium",       "group": 7,  "period": 6},
    {"z": 76, "symbol": "Os", "name": "Osmium",        "group": 8,  "period": 6},
    {"z": 77, "symbol": "Ir", "name": "Iridium",       "group": 9,  "period": 6},
    {"z": 78, "symbol": "Pt", "name": "Platinum",      "group": 10, "period": 6},
    {"z": 79, "symbol": "Au", "name": "Gold",          "group": 11, "period": 6},
    {"z": 80, "symbol": "Hg", "name": "Mercury",       "group": 12, "period": 6},
    {"z": 81, "symbol": "Tl", "name": "Thallium",      "group": 13, "period": 6},
    {"z": 82, "symbol": "Pb", "name": "Lead",          "group": 14, "period": 6},
    {"z": 83, "symbol": "Bi", "name": "Bismuth",       "group": 15, "period": 6},
    {"z": 84, "symbol": "Po", "name": "Polonium",      "group": 16, "period": 6},
    {"z": 85, "symbol": "At", "name": "Astatine",      "group": 17, "period": 6},
    {"z": 86, "symbol": "Rn", "name": "Radon",         "group": 18, "period": 6},
    # period 7 (includes actinides)
    {"z": 87, "symbol": "Fr", "name": "Francium",      "group": 1,  "period": 7},
    {"z": 88, "symbol": "Ra", "name": "Radium",        "group": 2,  "period": 7},
    {"z": 89, "symbol": "Ac", "name": "Actinium",      "group": 3,  "period": 7},
    {"z": 90, "symbol": "Th", "name": "Thorium",       "group": 3,  "period": 7},
    {"z": 91, "symbol": "Pa", "name": "Protactinium",   "group": 3,  "period": 7},
    {"z": 92, "symbol": "U",  "name": "Uranium",        "group": 3,  "period": 7},
    {"z": 93, "symbol": "Np", "name": "Neptunium",     "group": 3,  "period": 7},
    {"z": 94, "symbol": "Pu", "name": "Plutonium",     "group": 3,  "period": 7},
    {"z": 95, "symbol": "Am", "name": "Americium",     "group": 3,  "period": 7},
    {"z": 96, "symbol": "Cm", "name": "Curium",        "group": 3,  "period": 7},
    {"z": 97, "symbol": "Bk", "name": "Berkelium",     "group": 3,  "period": 7},
    {"z": 98, "symbol": "Cf", "name": "Californium",   "group": 3,  "period": 7},
    {"z": 99, "symbol": "Es", "name": "Einsteinium",   "group": 3,  "period": 7},
    {"z": 100, "symbol": "Fm", "name": "Fermium",       "group": 3,  "period": 7},
    {"z": 101, "symbol": "Md", "name": "Mendelevium",   "group": 3,  "period": 7},
    {"z": 102, "symbol": "No", "name": "Nobelium",      "group": 3,  "period": 7},
    {"z": 103, "symbol": "Lr", "name": "Lawrencium",    "group": 3,  "period": 7},
    {"z": 104, "symbol": "Rf", "name": "Rutherfordium", "group": 4,  "period": 7},
    {"z": 105, "symbol": "Db", "name": "Dubnium",       "group": 5,  "period": 7},
    {"z": 106, "symbol": "Sg", "name": "Seaborgium",    "group": 6,  "period": 7},
    {"z": 107, "symbol": "Bh", "name": "Bohrium",       "group": 7,  "period": 7},
    {"z": 108, "symbol": "Hs", "name": "Hassium",       "group": 8,  "period": 7},
    {"z": 109, "symbol": "Mt", "name": "Meitnerium",    "group": 9,  "period": 7},
    {"z": 110, "symbol": "Ds", "name": "Darmstadtium", "group": 10, "period": 7},
    {"z": 111, "symbol": "Rg", "name": "Roentgenium",  "group": 11, "period": 7},
    {"z": 112, "symbol": "Cn", "name": "Copernicium",   "group": 12, "period": 7},
    {"z": 113, "symbol": "Nh", "name": "Nihonium",      "group": 13, "period": 7},
    {"z": 114, "symbol": "Fl", "name": "Flerovium",     "group": 14, "period": 7},
    {"z": 115, "symbol": "Mc", "name": "Moscovium",     "group": 15, "period": 7},
    {"z": 116, "symbol": "Lv", "name": "Livermorium",   "group": 16, "period": 7},
    {"z": 117, "symbol": "Ts", "name": "Tennessine",    "group": 17, "period": 7},
    {"z": 118, "symbol": "Og", "name": "Oganesson",     "group": 18, "period": 7},
]


def build_position_map() -> Dict[Tuple[int, int], Optional[int]]:
    """Return a mapping of (period, group) to atomic number (z).

    The conventional periodic table arranges elements into a 7×18 grid for the
    main block, with the lanthanide and actinide series displayed separately
    beneath.  For simplicity, we return a dictionary keyed by (row, column)
    where row 1–7 correspond to periods 1–7 and column 1–18 correspond to
    groups.  Positions that should be occupied by lanthanide/actinide
    placeholders are mapped to None; the calling code inserts placeholder
    strings there.

    Returns:
        Dict mapping (period, group) -> atomic number or None.
    """
    pos: Dict[Tuple[int, int], Optional[int]] = {}
    # initialise all positions to None
    for p in range(1, 8):
        for g in range(1, 19):
            pos[(p, g)] = None
    # map main table elements (excluding lanthanides and actinides)
    for elem in PERIODIC_TABLE:
        z = elem["z"]
        period = elem["period"]
        group = elem["group"]
        # Only place main‑block elements (lanthanides and actinides later)
        if 57 <= z <= 71 or 89 <= z <= 103:
            continue
        pos[(period, group)] = z
    return pos


def assign_f_block() -> Tuple[List[int], List[int]]:
    """Return ordered lists of atomic numbers for lanthanides and actinides.

    Lanthanides are elements 57–71 and actinides are elements 89–103.  The
    returned lists are sorted in increasing atomic number.

    Returns:
        (lanthanides, actinides)
    """
    lanths = [elem["z"] for elem in PERIODIC_TABLE if 57 <= elem["z"] <= 71]
    actins = [elem["z"] for elem in PERIODIC_TABLE if 89 <= elem["z"] <= 103]
    return lanths, actins


def fetch_sheet_data(api_url: str, sheet_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve data from the Apps Script endpoint.

    Args:
        api_url: The URL of the Apps Script web app (ending in `/exec`).
        sheet_id: Optional spreadsheet ID; passed as the `id` parameter if
            supplied.  The Apps Script can ignore this if the ID is
            hardcoded.

    Returns:
        The parsed JSON response.

    Raises:
        RuntimeError: If the request fails or returns invalid JSON.
    """
    params: Dict[str, str] = {}
    if sheet_id:
        params["id"] = sheet_id
    try:
        response = requests.get(api_url, params=params, timeout=30)
    except Exception as exc:
        raise RuntimeError(f"HTTP request to {api_url} failed: {exc}") from exc
    if response.status_code != 200:
        raise RuntimeError(
            f"Endpoint returned status {response.status_code}: {response.text[:200]}"
        )
    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        preview = response.text.strip().splitlines()[:5]
        raise RuntimeError(
            f"Failed to parse JSON from endpoint. Response begins: {preview}"
        ) from exc
    # sanity checks
    if not isinstance(data, dict) or "elements" not in data:
        raise RuntimeError(
            f"Unexpected payload structure; expected a dict with an 'elements' key: {data}"
        )
    return data


@dataclass
class Sample:
    value: str
    state: str
    color: str


@dataclass
class SheetElement:
    z: int
    symbol: str
    name: str
    samples: List[Sample]


def assemble_elements(
    data: Dict[str, Any],
    label_colors: Dict[str, str],
) -> List[SheetElement]:
    """Combine sheet information with periodic table metadata.

    Args:
        data: JSON data returned from Apps Script.
        label_colors: Mapping from state label to colour hex (e.g. `"da comprare": "#ff0000"`).

    Returns:
        A list of SheetElement objects in order of atomic number.
    """
    # Build lookup from symbol to sample info
    sheet_map: Dict[str, Dict[str, Any]] = {}
    for entry in data.get("elements", []):
        sym = str(entry.get("symbol", "")).strip()
        if not sym:
            continue
        sheet_map[sym] = entry
    elements: List[SheetElement] = []
    for meta in PERIODIC_TABLE:
        sym = meta["symbol"]
        name = meta["name"]
        z = meta["z"]
        samples_info: List[Sample] = []
        entry = sheet_map.get(sym)
        if entry:
            for s in entry.get("samples", []):
                # normalise blanks
                val = s.get("value", "")
                if val is None:
                    val = ""
                val_str = str(val)
                state = str(s.get("state", "")).strip()
                color = str(s.get("color", "")).strip()
                # If state is present but colour missing, use label_colors mapping
                if state and not color:
                    color = label_colors.get(state, "")
                samples_info.append(Sample(value=val_str, state=state, color=color))
        else:
            # row missing from sheet; create empty samples
            samples_info = [Sample(value="", state="", color="") for _ in range(4)]
        # Ensure four samples
        while len(samples_info) < 4:
            samples_info.append(Sample(value="", state="", color=""))
        elements.append(SheetElement(z=z, symbol=sym, name=name, samples=samples_info))
    return elements


def build_cell_positions() -> Dict[Tuple[int, int], Optional[int]]:
    """Return a mapping of periodic table coordinates to atomic numbers.

    The returned dictionary maps (period, group) to the atomic number
    occupying that position.  The main-block positions (periods 1–7,
    groups 1–18) are filled via `build_position_map`, except that the
    f‑block anchor positions (6,3) and (7,3) are set to ``None`` so that
    the calling code can insert blank cells between the main table and the
    f‑block rows.  This leaves the main grid with 7 rows; later in
    ``render_html`` we insert an explicit empty row and then the
    lanthanide and actinide rows.

    Returns:
        A dictionary mapping (row, col) -> atomic number or None.
    """
    pos = build_position_map()
    # Reserve group 3 positions in periods 6 and 7 for placeholders
    pos[(6, 3)] = None
    pos[(7, 3)] = None
    return pos


def render_html(
    elements: List[SheetElement],
    data: Dict[str, Any],
    title: str = "Periodic Table with Samples",
) -> str:
    """Render the periodic table as an HTML string.

    Args:
        elements: List of SheetElement objects (length 118).
        data: Raw JSON from the Apps Script; must contain 'labelColors'.
        title: Document title.

    Returns:
        A complete HTML document as a string.
    """
    # Build quick lookup by atomic number
    elem_by_z = {e.z: e for e in elements}
    # Legend mapping label -> colour
    label_colors: Dict[str, str] = data.get("labelColors", {})
    # Determine the set of labels in order encountered in the legend range (if provided)
    legend_order: List[Tuple[str, str]] = []
    if "legend" in data:
        # legend is mapping colour -> label; invert while preserving order of appearance
        for color, label in data["legend"].items():
            legend_order.append((label, color))
    else:
        # fallback to label_colors dictionary (arbitrary order)
        for label, color in label_colors.items():
            legend_order.append((label, color))
    # Build base grid: 7 rows of main table followed by an empty row,
    # the lanthanide row and the actinide row.  The main‑block
    # positions are obtained from `build_cell_positions`; the f‑block
    # rows are appended later.
    pos_map = build_cell_positions()
    lanths, actins = assign_f_block()
    # HTML helpers
    def esc(s: str) -> str:
        return htmllib.escape(s, quote=True)
    def sanitize_label(label: str) -> str:
        """Sanitise a state label into a CSS‑friendly identifier."""
        s = label.lower()
        # Replace spaces and non‑alphanumeric characters with dashes
        out = []
        for ch in s:
            if ch.isalnum():
                out.append(ch)
            else:
                out.append('-')
        return "".join(out).strip('-')

    def render_sample_quarter(sample: Sample, idx: int) -> str:
        """Render a quarter of the element cell for one sample."""
        bg = sample.color if sample.color else "#eaeaea"
        label_index = str(idx + 1)
        tooltip_parts: List[str] = []
        if sample.state:
            tooltip_parts.append(esc(sample.state))
        if sample.value:
            tooltip_parts.append(esc(sample.value))
        tip_text = esc(" | ".join(tooltip_parts)) if tooltip_parts else ""
        # CSS class for filtering
        state_class = ''
        data_state = ''
        if sample.state:
            state_class = ' state-' + sanitize_label(sample.state)
            data_state = sanitize_label(sample.state)
        return (
            f'<div class="quarter{state_class}" style="background:{esc(bg)}" '
            f'data-state="{esc(data_state)}" data-tip="{tip_text}"><span class="sidx">{esc(label_index)}</span></div>'
        )
    # Compose cells: we will build 10 rows (7 main + 1 empty + lanth + actin)
    cells_html: List[str] = []
    for row in range(1, 11):  # rows 1..10
        for col in range(1, 19):
            z: Optional[int] = None
            # Rows 1–7: main periodic table
            if row <= 7:
                z = pos_map.get((row, col))
            # Row 8: spacer row (always empty)
            if row == 8:
                # all spacer cells get a special class for height adjustment
                cells_html.append('<div class="cell spacer empty"></div>')
                continue
            # Row 9: lanthanide series (f‑block 57–71)
            if row == 9 and 4 <= col <= 18:
                idx = col - 4
                if idx < len(lanths):
                    z = lanths[idx]
            # Row 10: actinide series (f‑block 89–103)
            if row == 10 and 4 <= col <= 18:
                idx = col - 4
                if idx < len(actins):
                    z = actins[idx]
            if z is None:
                cells_html.append('<div class="cell empty"></div>')
            else:
                e = elem_by_z.get(z)
                if e is None:
                    cells_html.append('<div class="cell empty"></div>')
                else:
                    tooltip_lines: List[str] = [f"{esc(e.name)}", f"Z={e.z}"]
                    for i, s in enumerate(e.samples):
                        parts: List[str] = []
                        if s.state:
                            parts.append(s.state)
                        if s.value:
                            parts.append(s.value)
                        if parts:
                            tooltip_lines.append(f"{i+1}: " + "; ".join(parts))
                    tip = esc("\n".join(tooltip_lines))
                    quarters = ''.join(
                        [render_sample_quarter(e.samples[i], i) for i in range(4)]
                    )
                    cell_html = (
                        # Store the atomic number on the element container for click events
                        f'<div class="cell element" data-tip="{tip}" data-z="{e.z}">'  # container with tooltip and data-z
                        f'<div class="number">{e.z}</div>'
                        f'<div class="symbol">{esc(e.symbol)}</div>'
                        f'<div class="samples">{quarters}</div>'
                        f'</div>'
                    )
                    cells_html.append(cell_html)
    # Build legend HTML (with data-state attributes for filters)
    legend_html: List[str] = []
    for label, color in legend_order:
        if not label:
            continue
        color_hex = color if color.startswith('#') else color
        # Sanitise label for CSS/data attribute
        state_id = sanitize_label(label)
        legend_html.append(
            f'<div class="legend-item" data-state="{esc(state_id)}"><span class="legend-colour" '
            f'style="background:{esc(color_hex)}"></span>{esc(label)}</div>'
        )
    legend_block = ''.join(legend_html)
    # Global CSS
    css = """
:root{
  --cell-size: clamp(60px, 5.5vw, 90px);
  --gap: 4px;
  --border-radius: 6px;
  --border-colour: rgba(0,0,0,0.2);
  --empty-bg: #f5f5f5;
  --empty-bg-dark: #222;
}
@media (prefers-color-scheme: dark){
  :root{
    --border-colour: rgba(255,255,255,0.25);
    --empty-bg: #20252a;
    --empty-bg-dark: #111;
  }
}
body{
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--empty-bg-dark);
  color: #eee;
}
h1{
  margin: 16px;
  font-size: 20px;
  text-align: center;
}
.table{
  display: grid;
  grid-template-columns: repeat(18, var(--cell-size));
  grid-auto-rows: var(--cell-size);
  gap: var(--gap);
  justify-content: center;
  padding: 16px;
}
.cell{
  position: relative;
  width: var(--cell-size);
  height: var(--cell-size);
  border: 1px solid var(--border-colour);
  border-radius: var(--border-radius);
  background: var(--empty-bg);
}
.cell.empty{
  background: transparent;
  border: none;
}
.cell.spacer{
  height: calc(var(--cell-size) / 2);
  background: transparent;
  border: none;
}
.cell.element{
  /* sempre sfondo chiaro e testo nero per leggibilità */
  background: #ffffff;
  color: #000000;
  overflow: hidden;
  cursor: default;
}
/* nessuna variazione in dark mode: il testo resta nero */
.symbol{
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
  padding: 4px 4px 2px 4px;
  color: #000000;
}
/* atomic number */
.number{
  position: absolute;
  top: 2px;
  right: 4px;
  font-size: 9px;
  color: #000000;
  pointer-events: none;
}
.samples{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  width: 100%;
  height: calc(100% - 24px);
}
.samples .quarter{
  position: relative;
  border: 1px solid var(--border-colour);
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #000000;
}
.samples .quarter .sidx{
  position: absolute;
  top: 2px;
  left: 2px;
  font-size: 9px;
  color: #444444;
  pointer-events: none;
}
  /* disable hover tooltip when popups are used */
  .cell[data-tip]:hover::after{
    display: none;
  }
.quarter.filtered{
  opacity: 0.15;
}
.legend-item{
  cursor: pointer;
}
.legend-item.active{
  box-shadow: 0 0 0 2px rgba(0,120,212,0.8);
}
.legend{
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  padding: 8px 16px 24px 16px;
  font-size: 13px;
}
.legend-item{
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--empty-bg);
  border: 1px solid var(--border-colour);
  border-radius: var(--border-radius);
  padding: 2px 6px;
  color: #000000; /* testi neri sui bottoni della legenda */
}
.legend-colour{
  width: 14px;
  height: 14px;
  border-radius: 3px;
  display: inline-block;
  border: 1px solid var(--border-colour);
}
  /* overlay and popup styles */
  .overlay{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    display: none;
    z-index: 999;
  }
  .overlay.visible{
    display: block;
  }
  .popup{
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: #ffffff;
    color: #000000;
    padding: 16px;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    max-width: 320px;
    min-width: 260px;
    display: none;
    z-index: 1000;
  }
  .popup.visible{
    display: block;
  }
"""
    # JavaScript to implement clickable filters on the legend
    # Construct a JavaScript object representing all elements and their samples.
    elements_js_entries = []
    for elem in elements:
        # Build a list of sample objects with state and value for JS
        samples_js = []
        for s in elem.samples:
            samples_js.append({
                "state": s.state,
                "value": s.value,
            })
        entry = {
            "z": elem.z,
            "symbol": elem.symbol,
            "name": elem.name,
            "samples": samples_js,
        }
        # Encode as JSON string
        elements_js_entries.append(f"{elem.z}: {json.dumps(entry)}")
    elements_js_object = "{\n    " + ",\n    ".join(elements_js_entries) + "\n  }"

    # JavaScript for filters and popups
    script = f"""
<script>
const elementsData = {elements_js_object};
document.addEventListener('DOMContentLoaded', function() {{
  const legendItems = document.querySelectorAll('.legend-item');
  legendItems.forEach(item => {{
    item.addEventListener('click', function() {{
      const state = this.getAttribute('data-state');
      legendItems.forEach(li => li.classList.toggle('active', li === this));
      document.querySelectorAll('.quarter').forEach(q => {{
        const qState = q.getAttribute('data-state');
        if (!state || state === '') {{
          q.classList.remove('filtered');
        }} else if (qState !== state) {{
          q.classList.add('filtered');
        }} else {{
          q.classList.remove('filtered');
        }}
      }});
    }});
  }});
  // Popup handling
  const overlay = document.getElementById('overlay');
  const popup = document.getElementById('popup');
  // Close popup when clicking outside
  overlay.addEventListener('click', function() {{
    overlay.classList.remove('visible');
    popup.classList.remove('visible');
  }});
  // Attach click handlers on element cells
  document.querySelectorAll('.cell.element').forEach(el => {{
    el.addEventListener('click', function(e) {{
      e.stopPropagation();
      const z = this.getAttribute('data-z');
      const info = elementsData[z];
      if (!info) return;
      let html = `<h2>${{info.symbol}} – ${{info.name}} (Z=${{info.z}})</h2><ul>`;
      info.samples.forEach((s, i) => {{
        const st = s.state ? s.state : '-';
        const val = s.value ? s.value : '';
        html += `<li><strong>Campione ${{i+1}}:</strong> ${{st}} – ${{val}}</li>`;
      }});
      html += '</ul>';
      popup.innerHTML = html;
      overlay.classList.add('visible');
      popup.classList.add('visible');
    }});
  }});
}});
</script>
"""
    html_parts = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        f"  <title>{esc(title)}</title>",
        "  <style>" + css + "</style>",
        "</head>",
        "<body>",
        f"  <h1>{esc(title)}</h1>",
        "  <div class=\"table\">",
        "    " + "".join(cells_html),
        "  </div>",
        "  <div class=\"legend\">",
        "    " + legend_block,
        "  </div>",
        # overlay and popup containers for click details
        "  <div id=\"overlay\" class=\"overlay\"></div>",
        "  <div id=\"popup\" class=\"popup\"></div>",
        script,
        "</body>",
        "</html>",
    ]
    return "\n".join(html_parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate periodic table HTML from a Google Apps Script JSON endpoint."
    )
    parser.add_argument(
        "--api-url",
        required=True,
        help="URL of the Apps Script web app endpoint (ending with /exec)",
    )
    parser.add_argument(
        "--id",
        dest="sheet_id",
        default=None,
        help="Spreadsheet ID to pass as ?id parameter (optional)",
    )
    parser.add_argument(
        "--title",
        default="Periodic Table – Sample tracker",
        help="Title of the generated HTML document",
    )
    parser.add_argument(
        "--output",
        default="periodic_table.html",
        help="Path to write the output HTML file",
    )
    parser.add_argument(
        "--dump-json",
        dest="dump_json",
        default=None,
        help="If set, write the raw JSON response to this file for debugging",
    )
    args = parser.parse_args()
    # Fetch data from the Apps Script
    data = fetch_sheet_data(args.api_url, args.sheet_id)
    # Optionally dump raw JSON
    if args.dump_json:
        with open(args.dump_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    # Extract legend label->colour mapping
    label_colors: Dict[str, str] = data.get("labelColors", {})
    # Build element objects
    elements = assemble_elements(data, label_colors)
    # Render HTML
    html_out = render_html(elements, data, title=args.title)
    # Write file
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html_out)
    except Exception as exc:
        raise RuntimeError(f"Failed to write output file {args.output}: {exc}") from exc
    print(f"Generated {args.output} successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())