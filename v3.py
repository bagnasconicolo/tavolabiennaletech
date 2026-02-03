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
    according to a legend defined in cells G2:G?.  The legend cells
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

NEW (single change requested):
- If the *symbol cell* in the Google Sheet (Column A) has background color
  #b8fb89, then in the generated HTML the background of the symbol banner
  (the `.symbol` div inside the element cell) is set to that green.

This requires the Apps Script JSON to include, for each element entry, a
field `symbolColor` (background of Column A). The script remains backward
compatible: if `symbolColor` is missing, nothing changes.

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
import os
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
    # NEW: background color of the symbol cell (Column A) as returned by Apps Script
    symbolColor: str = ""


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

        # NEW: read symbol cell background if present in JSON (backward-compatible)
        sym_bg = ""
        if entry:
            sym_bg = str(entry.get("symbolColor", "") or "").strip()

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

        elements.append(
            SheetElement(z=z, symbol=sym, name=name, samples=samples_info, symbolColor=sym_bg)
        )

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
    mobile_href: str = "mobile.html",
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
    # the lanthanide row and the actinide row.
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

    # NEW helper: normalize #RRGGBB strings
    def norm_hex(col: str) -> str:
        return (col or "").strip().lower().lstrip('#')

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

                    # NEW: if symbol cell bg is #b8fb89, set symbol banner background
                    symbol_style = ''
                    if norm_hex(getattr(e, 'symbolColor', '')) == 'b8fb89':
                        symbol_style = ' style="background:#b8fb89"'

                    cell_html = (
                        # Store the atomic number on the element container for click events
                        f'<div class="cell element" data-tip="{tip}" data-z="{e.z}">'  # container with tooltip and data-z
                        f'<div class="number">{e.z}</div>'
                        f'<div class="symbol"{symbol_style}>{esc(e.symbol)}</div>'
                        f'<div class="samples">{quarters}</div>'
                        f'</div>'
                    )
                    cells_html.append(cell_html)

    # Build legend HTML (with data-state attributes for filters and counts)
    legend_html: List[str] = []
    legend_html.append(
        '<div class="legend-item active" data-state="">'
        '<span class="legend-colour" style="background:linear-gradient(135deg,#e5e7eb,#ffffff)"></span>'
        'tutti<span class="legend-count" data-count-for="all">0</span></div>'
    )
    for label, color in legend_order:
        if not label:
            continue
        color_hex = color if color.startswith('#') else color
        state_id = sanitize_label(label)
        legend_html.append(
            f'<div class="legend-item" data-state="{esc(state_id)}"><span class="legend-colour" '
            f'style="background:{esc(color_hex)}"></span>{esc(label)}'
            f'<span class="legend-count" data-count-for="{esc(state_id)}">0</span></div>'
        )
    legend_html.append(
        '<div class="legend-item" data-state="completi">'
        '<span class="legend-colour" style="background:#93c47d"></span>'
        'completi<span class="legend-count" data-count-for="completi">0</span></div>'
    )
    legend_block = ''.join(legend_html)

    # Global CSS
    css = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Spectral:wght@400;600&display=swap');
:root{
  --cell-size: clamp(34px, 3.6vw, 76px);
  --gap: 6px;
  --border-radius: 6px;
  --border-colour: rgba(17, 23, 32, 0.12);
  --empty-bg: #f6f7f9;
  --ink: #0f172a;
  --paper: #ffffff;
  --accent: #0ea5a4;
  --accent-2: #f59e0b;
  --shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
}
:root[data-theme="dark"]{
  --border-colour: rgba(255,255,255,0.15);
  --empty-bg: #0f1115;
  --ink: #e5e7eb;
  --paper: #12151b;
  --accent: #22d3ee;
  --accent-2: #fbbf24;
  --shadow: 0 12px 28px rgba(0,0,0,0.4);
}
:root[data-theme="light"]{
  --border-colour: rgba(17, 23, 32, 0.12);
  --empty-bg: #f6f7f9;
  --ink: #0f172a;
  --paper: #ffffff;
  --accent: #0ea5a4;
  --accent-2: #f59e0b;
  --shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme]){
    --border-colour: rgba(255,255,255,0.15);
    --empty-bg: #0f1115;
    --ink: #e5e7eb;
    --paper: #12151b;
    --accent: #22d3ee;
    --accent-2: #fbbf24;
    --shadow: 0 12px 28px rgba(0,0,0,0.4);
  }
}
body{
  margin: 0;
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
  background:
    radial-gradient(1200px 800px at 80% -10%, rgba(14,165,164,0.15), transparent 60%),
    radial-gradient(900px 700px at 10% 0%, rgba(245,158,11,0.12), transparent 60%),
    var(--empty-bg);
  color: var(--ink);
  overflow-x: hidden;
}
.page{
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 18px 28px;
}
.hero{
  display: grid;
  gap: 8px;
  align-items: start;
  padding: 18px 20px;
  background: var(--paper);
  border: 1px solid var(--border-colour);
  border-radius: 16px;
  box-shadow: var(--shadow);
}
h1{
  margin: 0;
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
  font-size: clamp(22px, 3vw, 34px);
  letter-spacing: 0.3px;
  text-align: center;
}
.meta{
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: rgba(15,23,42,0.55);
  align-items: center;
  justify-content: center;
  text-align: center;
}
.meta-actions{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
:root[data-theme="dark"] .meta{
  color: rgba(229,231,235,0.85);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme]) .meta{
    color: rgba(229,231,235,0.85);
  }
}
.toolbar{
  display: grid;
  gap: 12px;
  margin-top: 16px;
}
.action-btn{
  border: 1px solid var(--border-colour);
  background: var(--paper);
  color: var(--ink);
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: transform 140ms ease, box-shadow 140ms ease;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.action-btn:hover{
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(15,23,42,0.15);
}
.action-btn.secondary{
  background: rgba(14,165,164,0.08);
}
.table-wrap{
  margin: 16px auto 0;
  padding: 10px 10px 12px;
  background: var(--paper);
  border: 1px solid var(--border-colour);
  border-radius: 16px;
  box-shadow: var(--shadow);
  width: 100%;
  max-width: 100%;
}
.table{
  display: grid;
  grid-template-columns: repeat(18, minmax(0, 1fr));
  gap: var(--gap);
  justify-content: center;
  width: 100%;
  margin: 0 auto;
}
.cell{
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  border: 1px solid var(--border-colour);
  border-radius: var(--border-radius);
  background: var(--empty-bg);
  box-shadow: 0 4px 12px rgba(15,23,42,0.08);
}
.cell.empty{
  background: transparent;
  border: none;
  box-shadow: none;
}
.cell.spacer{
  aspect-ratio: 2 / 1;
  background: transparent;
  border: none;
  box-shadow: none;
}
.cell.element{
  /* sempre sfondo chiaro e testo nero per leggibilità */
  background: #ffffff;
  color: #000000;
  overflow: hidden;
  cursor: default;
  transition: transform 160ms ease, box-shadow 160ms ease;
}
.cell.element.filtered{
  opacity: 0.15;
}
.cell.element.complete .symbol{
  background: #b8fb89;
  border-radius: 4px;
  padding: 2px 4px;
  display: inline-block;
}
@media (prefers-color-scheme: dark){
  .cell.element{
    background: #f8fafc;
    color: #0f172a;
  }
}
.cell.element:hover{
  transform: translateY(-2px);
  box-shadow: 0 10px 18px rgba(15,23,42,0.18);
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
  transition: opacity 120ms ease;
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
  box-shadow: 0 0 0 2px var(--accent);
}
.legend{
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  padding: 8px 0 6px 0;
  font-size: 13px;
}
.legend-item{
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--paper);
  border: 1px solid var(--border-colour);
  border-radius: var(--border-radius);
  padding: 2px 6px;
  color: var(--ink);
  transition: transform 140ms ease, box-shadow 140ms ease;
}
.legend-item[data-state="completi"]{
  background: linear-gradient(135deg, rgba(147,196,125,0.25), rgba(147,196,125,0.1));
  border-color: rgba(147,196,125,0.6);
  font-weight: 600;
}
.legend-item[data-state="completi"] .legend-colour{
  border-color: rgba(147,196,125,0.9);
}
.legend-count{
  margin-left: 4px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(15,23,42,0.08);
  font-size: 11px;
}
:root[data-theme="dark"] .legend-count{
  background: rgba(255,255,255,0.12);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme]) .legend-count{
    background: rgba(255,255,255,0.12);
  }
}
.legend-item:hover{
  transform: translateY(-1px);
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
    background: var(--paper);
    color: var(--ink);
    padding: 18px;
    border-radius: 14px;
    box-shadow: var(--shadow);
    max-width: 360px;
    min-width: 260px;
    display: none;
    z-index: 1000;
  }
  :root[data-theme="dark"] .popup{
    box-shadow: 0 0 0 1px rgba(255,255,255,0.18), 0 0 24px rgba(255,255,255,0.2), var(--shadow);
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme]) .popup{
      box-shadow: 0 0 0 1px rgba(255,255,255,0.18), 0 0 24px rgba(255,255,255,0.2), var(--shadow);
    }
  }
  .popup.visible{
    display: block;
  }
  .popup h2{
    margin: 0 0 8px 0;
    font-size: 18px;
  }
  .popup h2.complete{
    background: #93c47d;
    color: #0b2a14;
    padding: 6px 8px;
    border-radius: 8px;
    display: inline-block;
  }
  .popup ul{
    margin: 8px 0 0 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 6px;
    font-size: 13px;
  }
  .popup li{
    display: grid;
    gap: 2px;
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(15,23,42,0.04);
  }
  .popup .sample-row{
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .popup .sample-dot{
    width: 10px;
    height: 10px;
    border-radius: 999px;
    border: 1px solid rgba(0,0,0,0.15);
    display: inline-block;
    flex: 0 0 10px;
  }
  @media (prefers-color-scheme: dark){
    .popup li{
      background: rgba(255,255,255,0.05);
    }
  }
  .popup .close{
    position: absolute;
    top: 10px;
    right: 10px;
    border: none;
    background: rgba(15,23,42,0.06);
    color: var(--ink);
    font-size: 14px;
    border-radius: 999px;
    padding: 4px 8px;
    cursor: pointer;
  }
  .popup .close:hover{
    background: rgba(15,23,42,0.12);
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

    # Build state->color mapping for popup dots
    state_colors = {
        sanitize_label(label): color
        for label, color in label_colors.items()
        if label
    }
    state_colors_js = json.dumps(state_colors)

    # JavaScript for filters and popups
    script = f"""
<script>
const elementsData = {elements_js_object};
const stateColors = {state_colors_js};
document.addEventListener('DOMContentLoaded', function() {{
  const legendItems = Array.from(document.querySelectorAll('.legend-item'));
  const quarters = Array.from(document.querySelectorAll('.quarter'));
  const elementCells = Array.from(document.querySelectorAll('.cell.element'));
  const legendCounts = Array.from(document.querySelectorAll('.legend-count'));
  const deployMetaEl = document.getElementById('deploy-meta');
  const themeToggle = document.getElementById('theme-toggle');
  // Popup handling
  const overlay = document.getElementById('overlay');
  const popup = document.getElementById('popup');

  function setActiveLegend(target) {{
    legendItems.forEach(li => li.classList.toggle('active', li === target));
  }}

  function applyFilter(state) {{
    if (state === 'completi') {{
      quarters.forEach(q => q.classList.remove('filtered'));
      elementCells.forEach(cell => {{
        cell.classList.toggle('filtered', !cell.classList.contains('complete'));
      }});
      return;
    }}
    elementCells.forEach(cell => cell.classList.remove('filtered'));
    quarters.forEach(q => {{
      const qState = q.getAttribute('data-state');
      if (!state) {{
        q.classList.remove('filtered');
      }} else if (qState !== state) {{
        q.classList.add('filtered');
      }} else {{
        q.classList.remove('filtered');
      }}
    }});
  }}

  legendItems.forEach(item => {{
    item.addEventListener('click', function() {{
      const state = this.getAttribute('data-state');
      const isActive = this.classList.contains('active');
      if (isActive && state) {{
        const allItem = legendItems.find(li => li.getAttribute('data-state') === '');
        if (allItem) {{
          setActiveLegend(allItem);
        }}
        applyFilter('');
        return;
      }}
      setActiveLegend(this);
      applyFilter(state);
    }});
  }});

  function buildStats() {{
    const counts = {{}};
    legendCounts.forEach(el => {{
      const key = el.getAttribute('data-count-for');
      if (key && key !== 'all') {{
        counts[key] = 0;
      }}
    }});
    quarters.forEach(q => {{
      const st = q.getAttribute('data-state');
      if (counts[st] !== undefined) {{
        counts[st] += 1;
      }}
    }});
    elementCells.forEach(cell => {{
      if (cell.classList.contains('complete')) {{
        if (counts.completi !== undefined) {{
          counts.completi += 1;
        }}
      }}
    }});
    const total = Object.values(counts).reduce((acc, val) => acc + val, 0);
    legendCounts.forEach(el => {{
      const key = el.getAttribute('data-count-for');
      if (key === 'all') {{
        el.textContent = total;
      }} else if (counts[key] !== undefined) {{
        el.textContent = counts[key];
      }}
    }});
  }}

  function applyTheme(mode) {{
    const root = document.documentElement;
    if (!root) return;
    if (mode === 'dark' || mode === 'light') {{
      root.setAttribute('data-theme', mode);
    }} else {{
      root.removeAttribute('data-theme');
    }}
    if (themeToggle) {{
      themeToggle.textContent = mode === 'dark' ? 'Light mode' : 'Dark mode';
    }}
  }}

  function initTheme() {{
    if (!themeToggle) return;
    const stored = localStorage.getItem('theme');
    let mode = stored;
    if (!mode) {{
      mode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }}
    applyTheme(mode);
    themeToggle.addEventListener('click', () => {{
      const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      const next = current === 'dark' ? 'light' : 'dark';
      localStorage.setItem('theme', next);
      applyTheme(next);
    }});
  }}

  async function loadLatestCommit() {{
    if (!deployMetaEl) return;
    const owner = 'bagnasconicolo';
    const repo = 'tavolabiennaletech';
    try {{
      const res = await fetch(`https://api.github.com/repos/${{owner}}/${{repo}}/commits?per_page=1`, {{
        headers: {{ 'Accept': 'application/vnd.github+json' }}
      }});
      if (!res.ok) throw new Error('GitHub API error');
      const commits = await res.json();
      const latest = Array.isArray(commits) ? commits[0] : null;
      const committedAt = latest?.commit?.committer?.date || latest?.commit?.author?.date;
      if (!committedAt) throw new Error('No commit data');
      const dt = new Date(committedAt);
      const formatted = dt.toLocaleString('it-IT', {{
        day: '2-digit',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      }});
      deployMetaEl.textContent = `Ultimo commit: ${{formatted}}`;
    }} catch (err) {{
      deployMetaEl.textContent = 'Ultimo commit: non disponibile';
    }}
  }}

  function computeCompleteElements() {{
    elementCells.forEach(cell => {{
      const symbolEl = cell.querySelector('.symbol');
      if (!symbolEl) return;
      const inlineBg = symbolEl.style.backgroundColor || symbolEl.style.background;
      const complete = Boolean(inlineBg && inlineBg !== 'transparent' && inlineBg !== 'initial');
      cell.classList.toggle('complete', complete);
    }});
  }}

  function closePopup() {{
    overlay.classList.remove('visible');
    popup.classList.remove('visible');
  }}

  overlay.addEventListener('click', closePopup);
  document.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape') {{
      closePopup();
    }}
  }});

  // Attach click handlers on element cells
  elementCells.forEach(el => {{
    el.addEventListener('click', function(e) {{
      e.stopPropagation();
      const z = this.getAttribute('data-z');
      const info = elementsData[z];
      if (!info) return;
      const complete = this.classList.contains('complete');
      let html = `<button class="close" aria-label="Chiudi">Chiudi</button>`;
      html += `<h2 class="${{complete ? 'complete' : ''}}">${{info.symbol}} – ${{info.name}} (Z=${{info.z}})</h2><ul>`;
      info.samples.forEach((s, i) => {{
        const st = s.state ? s.state : 'non definito';
        const val = s.value ? s.value : '—';
        const key = st.replace(/\\s+/g, '-').toLowerCase();
        const color = stateColors[key] || '#e5e7eb';
        html += `<li><span class="sample-row"><span class="sample-dot" style="background:${{color}}"></span><strong>Campione ${{i+1}}:</strong></span> ${{st}} · ${{val}}</li>`;
      }});
      html += '</ul>';
      popup.innerHTML = html;
      popup.querySelector('.close').addEventListener('click', closePopup);
      overlay.classList.add('visible');
      popup.classList.add('visible');
    }});
  }});

  computeCompleteElements();
  buildStats();
  initTheme();
  loadLatestCommit();
}});
</script>
"""

    html_parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        f"  <title>{esc(title)}</title>",
        "  <style>" + css + "</style>",
        "</head>",
        "<body>",
        "  <div class=\"page\">",
        "    <section class=\"hero\">",
        f"      <h1>{esc(title)}</h1>",
        "      <div class=\"meta\">",
        "        <span id=\"deploy-meta\">Ultimo commit: in caricamento…</span>",
        "        <div class=\"meta-actions\">",
        "          <button id=\"theme-toggle\" class=\"action-btn\" type=\"button\">Dark mode</button>",
        f"          <a class=\"action-btn secondary\" href=\"{esc(mobile_href)}\">Vista mobile</a>",
        "        </div>",
        "      </div>",
        "    </section>",
        "",
        "    <div class=\"table-wrap\">",
        "      <div class=\"table\">",
        "    " + "".join(cells_html),
        "      </div>",
        "    </div>",
        "",
        "    <section class=\"toolbar\">",
        "      <div class=\"legend\">",
        "        " + legend_block,
        "      </div>",
        "    </section>",
        "  </div>",
        # overlay and popup containers for click details
        "  <div id=\"overlay\" class=\"overlay\"></div>",
        "  <div id=\"popup\" class=\"popup\"></div>",
        script,
        "</body>",
        "</html>",
    ]
    return "\n".join(html_parts)


def render_mobile_html(
    elements: List[SheetElement],
    data: Dict[str, Any],
    title: str = "Periodic Table – Mobile",
    desktop_href: str = "index.html",
) -> str:
    """Render a mobile-friendly HTML page with a list view of elements."""
    label_colors: Dict[str, str] = data.get("labelColors", {})

    legend_order: List[Tuple[str, str]] = []
    if "legend" in data:
        for color, label in data["legend"].items():
            legend_order.append((label, color))
    else:
        for label, color in label_colors.items():
            legend_order.append((label, color))

    def esc(s: str) -> str:
        return htmllib.escape(s, quote=True)

    def sanitize_label(label: str) -> str:
        s = label.lower()
        out = []
        for ch in s:
            if ch.isalnum():
                out.append(ch)
            else:
                out.append('-')
        return "".join(out).strip('-')

    def norm_hex(col: str) -> str:
        return (col or "").strip().lower().lstrip('#')

    chips_html: List[str] = []
    chips_html.append(
        '<button class="filter-chip active" data-state="">'
        '<span class="chip-dot" style="background:linear-gradient(135deg,#e5e7eb,#ffffff)"></span>'
        'tutti<span class="chip-count" data-count-for="all">0</span></button>'
    )
    for label, color in legend_order:
        if not label:
            continue
        state_id = sanitize_label(label)
        color_hex = color if color.startswith('#') else color
        chips_html.append(
            f'<button class="filter-chip" data-state="{esc(state_id)}">'
            f'<span class="chip-dot" style="background:{esc(color_hex)}"></span>'
            f'{esc(label)}<span class="chip-count" data-count-for="{esc(state_id)}">0</span></button>'
        )
    chips_html.append(
        '<button class="filter-chip" data-state="completi">'
        '<span class="chip-dot" style="background:#93c47d"></span>'
        'completi<span class="chip-count" data-count-for="completi">0</span></button>'
    )

    cards_html: List[str] = []
    for e in elements:
        states = []
        for s in e.samples:
            if s.state:
                states.append(sanitize_label(s.state))
        unique_states = sorted(set([s for s in states if s]))
        states_attr = " ".join(unique_states)
        is_complete = norm_hex(getattr(e, "symbolColor", "")) == "b8fb89"
        complete_class = " complete" if is_complete else ""
        symbol_style = ' style="background:#b8fb89"' if is_complete else ""

        samples_html: List[str] = []
        for idx, s in enumerate(e.samples):
            st = s.state if s.state else "non definito"
            val = s.value if s.value else "—"
            color = s.color if s.color else "#e5e7eb"
            samples_html.append(
                f'<div class="sample">'
                f'<span class="sample-dot" style="background:{esc(color)}"></span>'
                f'<div class="sample-main">Campione {idx+1}</div>'
                f'<div class="sample-meta">{esc(st)} · {esc(val)}</div>'
                f'</div>'
            )
        cards_html.append(
            f'<article class="element-card{complete_class}" '
            f'data-states="{esc(states_attr)}" '
            f'data-search="{esc(f"{e.symbol} {e.name} {e.z}")}" '
            f'data-symbol="{esc(e.symbol)}" data-name="{esc(e.name)}" data-z="{e.z}">'
            f'<div class="card-top">'
            f'<div class="symbol-badge"{symbol_style}>{esc(e.symbol)}</div>'
            f'<div class="card-title">'
            f'<div class="element-name">{esc(e.name)}</div>'
            f'<div class="element-meta">Z={e.z}</div>'
            f'</div>'
            f'<div class="card-tag">{ "Completo" if is_complete else "In corso" }</div>'
            f'</div>'
            f'<div class="samples-list">{"".join(samples_html)}</div>'
            f'</article>'
        )

    css = """
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Spectral:wght@400;600&display=swap');
:root{
  --border-colour: rgba(17, 23, 32, 0.12);
  --empty-bg: #f6f7f9;
  --ink: #0f172a;
  --paper: #ffffff;
  --accent: #0ea5a4;
  --accent-2: #f59e0b;
  --shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
}
:root[data-theme="dark"]{
  --border-colour: rgba(255,255,255,0.15);
  --empty-bg: #0f1115;
  --ink: #e5e7eb;
  --paper: #12151b;
  --accent: #22d3ee;
  --accent-2: #fbbf24;
  --shadow: 0 12px 28px rgba(0,0,0,0.4);
}
:root[data-theme="light"]{
  --border-colour: rgba(17, 23, 32, 0.12);
  --empty-bg: #f6f7f9;
  --ink: #0f172a;
  --paper: #ffffff;
  --accent: #0ea5a4;
  --accent-2: #f59e0b;
  --shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme]){
    --border-colour: rgba(255,255,255,0.15);
    --empty-bg: #0f1115;
    --ink: #e5e7eb;
    --paper: #12151b;
    --accent: #22d3ee;
    --accent-2: #fbbf24;
    --shadow: 0 12px 28px rgba(0,0,0,0.4);
  }
}
body{
  margin: 0;
  font-family: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
  background:
    radial-gradient(1000px 700px at 85% -10%, rgba(14,165,164,0.14), transparent 60%),
    radial-gradient(800px 600px at 12% 0%, rgba(245,158,11,0.14), transparent 60%),
    var(--empty-bg);
  color: var(--ink);
}
.page{
  max-width: 980px;
  margin: 0 auto;
  padding: 18px 16px 32px;
}
.hero{
  display: grid;
  gap: 10px;
  padding: 18px 18px;
  background: var(--paper);
  border: 1px solid var(--border-colour);
  border-radius: 16px;
  box-shadow: var(--shadow);
}
h1{
  margin: 0;
  font-size: clamp(20px, 4vw, 30px);
  letter-spacing: 0.2px;
}
.meta{
  display: grid;
  gap: 8px;
  font-size: 12px;
  color: rgba(15,23,42,0.55);
}
:root[data-theme="dark"] .meta{
  color: rgba(229,231,235,0.8);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme]) .meta{
    color: rgba(229,231,235,0.8);
  }
}
.meta-actions{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.action-btn{
  border: 1px solid var(--border-colour);
  background: var(--paper);
  color: var(--ink);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  transition: transform 140ms ease, box-shadow 140ms ease;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.action-btn:hover{
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(15,23,42,0.15);
}
.action-btn.secondary{
  background: rgba(14,165,164,0.08);
}
.search-panel{
  margin-top: 16px;
  background: var(--paper);
  border: 1px solid var(--border-colour);
  border-radius: 16px;
  padding: 14px;
  box-shadow: var(--shadow);
  display: grid;
  gap: 12px;
}
.search-input{
  width: 100%;
  border: 1px solid var(--border-colour);
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 14px;
  background: var(--empty-bg);
  color: var(--ink);
}
.filters{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.filter-chip{
  border: 1px solid var(--border-colour);
  background: var(--paper);
  color: var(--ink);
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.filter-chip.active{
  box-shadow: 0 0 0 2px var(--accent);
}
.chip-dot{
  width: 12px;
  height: 12px;
  border-radius: 4px;
  border: 1px solid var(--border-colour);
}
.chip-count{
  margin-left: 2px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(15,23,42,0.08);
  font-size: 11px;
}
:root[data-theme="dark"] .chip-count{
  background: rgba(255,255,255,0.12);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme]) .chip-count{
    background: rgba(255,255,255,0.12);
  }
}
.results{
  font-size: 12px;
  color: rgba(15,23,42,0.55);
}
:root[data-theme="dark"] .results{
  color: rgba(229,231,235,0.7);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme]) .results{
    color: rgba(229,231,235,0.7);
  }
}
.card-grid{
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}
.element-card{
  background: var(--paper);
  border: 1px solid var(--border-colour);
  border-radius: 16px;
  padding: 12px;
  box-shadow: var(--shadow);
  display: grid;
  gap: 10px;
}
.element-card.hidden{
  display: none;
}
.card-top{
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px;
  align-items: center;
}
.symbol-badge{
  width: 44px;
  height: 44px;
  border-radius: 12px;
  border: 1px solid var(--border-colour);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
  background: #ffffff;
  color: #000000;
}
.element-card.complete .symbol-badge{
  background: #b8fb89;
}
.card-title{
  display: grid;
  gap: 2px;
}
.element-name{
  font-weight: 600;
  font-size: 15px;
}
.element-meta{
  font-size: 12px;
  color: rgba(15,23,42,0.55);
}
.card-tag{
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(14,165,164,0.12);
  color: var(--ink);
}
.element-card.complete .card-tag{
  background: rgba(147,196,125,0.25);
}
.samples-list{
  display: grid;
  gap: 8px;
}
.sample{
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto auto;
  gap: 4px 8px;
  align-items: center;
  padding: 8px;
  border-radius: 10px;
  background: rgba(15,23,42,0.04);
}
@media (prefers-color-scheme: dark){
  .sample{
    background: rgba(255,255,255,0.06);
  }
}
.sample-dot{
  width: 12px;
  height: 12px;
  border-radius: 999px;
  border: 1px solid rgba(0,0,0,0.15);
  grid-row: 1 / span 2;
}
.sample-main{
  font-size: 12px;
  font-weight: 600;
}
.sample-meta{
  font-size: 12px;
  color: rgba(15,23,42,0.68);
}
:root[data-theme="dark"] .sample-meta{
  color: rgba(229,231,235,0.7);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme]) .sample-meta{
    color: rgba(229,231,235,0.7);
  }
}
"""

    script = """
<script>
document.addEventListener('DOMContentLoaded', function() {
  const cards = Array.from(document.querySelectorAll('.element-card'));
  const chips = Array.from(document.querySelectorAll('.filter-chip'));
  const counts = Array.from(document.querySelectorAll('.chip-count'));
  const searchInput = document.getElementById('search-input');
  const resultsEl = document.getElementById('results-count');
  const deployMetaEl = document.getElementById('deploy-meta');
  const themeToggle = document.getElementById('theme-toggle');

  function setActiveChip(target) {
    chips.forEach(chip => chip.classList.toggle('active', chip === target));
  }

  function getActiveState() {
    const active = chips.find(chip => chip.classList.contains('active'));
    return active ? (active.getAttribute('data-state') || '') : '';
  }

  function updateCounts() {
    const map = {};
    counts.forEach(el => {
      const key = el.getAttribute('data-count-for');
      if (key) map[key] = 0;
    });
    cards.forEach(card => {
      const stateList = (card.getAttribute('data-states') || '').split(' ').filter(Boolean);
      stateList.forEach(st => {
        if (map[st] !== undefined) map[st] += 1;
      });
      if (card.classList.contains('complete') && map.completi !== undefined) {
        map.completi += 1;
      }
    });
    const total = cards.length;
    counts.forEach(el => {
      const key = el.getAttribute('data-count-for');
      if (key === 'all') {
        el.textContent = total;
      } else if (map[key] !== undefined) {
        el.textContent = map[key];
      }
    });
  }

  function applyFilters() {
    const state = getActiveState();
    const term = (searchInput && searchInput.value ? searchInput.value.trim().toLowerCase() : '');
    let visibleCount = 0;
    cards.forEach(card => {
      let visible = true;
      if (state === 'completi') {
        visible = card.classList.contains('complete');
      } else if (state) {
        const stateList = (card.getAttribute('data-states') || '').split(' ').filter(Boolean);
        visible = stateList.includes(state);
      }
      if (term) {
        const hay = (card.getAttribute('data-search') || '').toLowerCase();
        if (!hay.includes(term)) visible = false;
      }
      card.classList.toggle('hidden', !visible);
      if (visible) visibleCount += 1;
    });
    if (resultsEl) {
      resultsEl.textContent = `${visibleCount} / ${cards.length}`;
    }
  }

  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      setActiveChip(chip);
      applyFilters();
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', applyFilters);
  }

  function applyTheme(mode) {
    const root = document.documentElement;
    if (!root) return;
    if (mode === 'dark' || mode === 'light') {
      root.setAttribute('data-theme', mode);
    } else {
      root.removeAttribute('data-theme');
    }
    if (themeToggle) {
      themeToggle.textContent = mode === 'dark' ? 'Light mode' : 'Dark mode';
    }
  }

  function initTheme() {
    if (!themeToggle) return;
    const stored = localStorage.getItem('theme');
    let mode = stored;
    if (!mode) {
      mode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    applyTheme(mode);
    themeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      const next = current === 'dark' ? 'light' : 'dark';
      localStorage.setItem('theme', next);
      applyTheme(next);
    });
  }

  async function loadLatestCommit() {
    if (!deployMetaEl) return;
    const owner = 'bagnasconicolo';
    const repo = 'tavolabiennaletech';
    try {
      const res = await fetch(`https://api.github.com/repos/${owner}/${repo}/commits?per_page=1`, {
        headers: { 'Accept': 'application/vnd.github+json' }
      });
      if (!res.ok) throw new Error('GitHub API error');
      const commits = await res.json();
      const latest = Array.isArray(commits) ? commits[0] : null;
      const committedAt = latest?.commit?.committer?.date || latest?.commit?.author?.date;
      if (!committedAt) throw new Error('No commit data');
      const dt = new Date(committedAt);
      const formatted = dt.toLocaleString('it-IT', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
      deployMetaEl.textContent = `Ultimo commit: ${formatted}`;
    } catch (err) {
      deployMetaEl.textContent = 'Ultimo commit: non disponibile';
    }
  }

  updateCounts();
  applyFilters();
  initTheme();
  loadLatestCommit();
});
</script>
"""

    html_parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
        f"  <title>{esc(title)}</title>",
        "  <style>" + css + "</style>",
        "</head>",
        "<body>",
        "  <div class=\"page\">",
        "    <section class=\"hero\">",
        f"      <h1>{esc(title)}</h1>",
        "      <div class=\"meta\">",
        "        <span id=\"deploy-meta\">Ultimo commit: in caricamento…</span>",
        "        <div class=\"meta-actions\">",
        "          <button id=\"theme-toggle\" class=\"action-btn\" type=\"button\">Dark mode</button>",
        f"          <a class=\"action-btn secondary\" href=\"{esc(desktop_href)}\">Vista tabella</a>",
        "        </div>",
        "      </div>",
        "    </section>",
        "    <section class=\"search-panel\">",
        "      <input id=\"search-input\" class=\"search-input\" type=\"search\" placeholder=\"Cerca per simbolo, nome o numero…\" aria-label=\"Cerca elementi\">",
        "      <div class=\"filters\">",
        "        " + "".join(chips_html),
        "      </div>",
        "      <div class=\"results\">Elementi visibili: <span id=\"results-count\">0</span></div>",
        "    </section>",
        "    <section class=\"card-grid\">",
        "      " + "".join(cards_html),
        "    </section>",
        "  </div>",
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
        "--mobile-output",
        dest="mobile_output",
        default=None,
        help="Optional path for the mobile HTML output (default: mobile.html next to --output)",
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

    # Render HTML (desktop + mobile)
    mobile_out = args.mobile_output
    if not mobile_out:
        if args.output.lower().endswith(".html"):
            base_dir = os.path.dirname(os.path.abspath(args.output))
            mobile_out = os.path.join(base_dir, "mobile.html")
        else:
            mobile_out = "mobile.html"
    desktop_dir = os.path.dirname(os.path.abspath(args.output))
    mobile_dir = os.path.dirname(os.path.abspath(mobile_out))
    mobile_href = os.path.relpath(mobile_out, start=desktop_dir).replace(os.sep, "/")
    desktop_href = os.path.relpath(args.output, start=mobile_dir).replace(os.sep, "/")

    html_out = render_html(elements, data, title=args.title, mobile_href=mobile_href)
    mobile_title = f"{args.title} – Mobile"
    html_mobile = render_mobile_html(elements, data, title=mobile_title, desktop_href=desktop_href)

    # Write file
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html_out)
        with open(mobile_out, "w", encoding="utf-8") as f:
            f.write(html_mobile)
    except Exception as exc:
        raise RuntimeError(f"Failed to write output file {args.output}: {exc}") from exc

    print(f"Generated {args.output} successfully.")
    print(f"Generated {mobile_out} successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
