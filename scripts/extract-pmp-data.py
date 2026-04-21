#!/usr/bin/env python3
"""
Extract per-survey weighted PCI history from MicroPAVER .mdb files
(plus one .xlsx for San Juan Capistrano) and write
src/data/pmp-history.json for the home-page PCI-over-time charts.

Rules (per handoff doc + user clarifications):
- Weighted PCI per survey = Σ(PCI × area) / Σ(area), over sections inspected in that survey
- Area = SYS_Length × SYS_Width + SYS_Area Adjustment
- Include only Branch.UID_BUse == 'ROADWAY', excluding branches whose Name starts with 'ALLEY'
- Cluster inspection dates into surveys by a 180-day gap
- Drop surveys with weighted PCI == 100 (user: placeholder/uninspected)
- Drop surveys with fewer than 10 contributing sections (noise)
- SJC xlsx has no area column → simple mean instead of weighted mean
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from statistics import median

import openpyxl

# (date, pci, area, section_uid)
Sample = tuple[datetime, float, float, str]

PMP_DIR = Path("/Users/claudeai/Projects/Website/PMP graphic")
OUT = Path(__file__).resolve().parent.parent / "src" / "data" / "pmp-history.json"

MICROPAVER_CITIES = [
    ("Orange", "Orange 5-5-24.mdb"),
    ("Huntington Beach", "HB 5-31-24.mdb"),
    ("Ontario", "Ontario 12-10-24.mdb"),
    ("Fountain Valley", "Fountain Valley 3-12-26.mdb"),
]
SJC_HIST_XLSX = "SanJuanCapistrano_HistoricalPCI-MyRoads.xlsx"
SJC_SECTIONS_XLSX = "Sections.xlsx"

MIN_COVERAGE_FRACTION = 0.10        # FY must touch ≥ 10% of network sections to count
MAX_SURVEY_AVG_PCI = 99.0           # FY average ≥ this = placeholder import, not real
ALLEY_RE = re.compile(r"^\s*alley\b", re.IGNORECASE)


def mdb_csv(mdb: Path, table: str) -> list[dict]:
    r = subprocess.run(
        ["mdb-export", str(mdb), table], capture_output=True, text=True, check=True
    )
    return list(csv.DictReader(r.stdout.splitlines()))


def parse_date(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in (
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%y %I:%M:%S %p",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def to_float(s: str) -> float | None:
    try:
        return float(s) if s not in (None, "") else None
    except (TypeError, ValueError):
        return None


def extract_micropaver(mdb: Path) -> list[dict]:
    """Return a list of survey records: {year, start, end, pci, n_sections, area_sf}."""
    # Included branches: ROADWAY only, no alleys
    branches = mdb_csv(mdb, "Branch")
    included_branches = {
        b["UID_BUniqueID"]
        for b in branches
        if b.get("UID_BUse") == "ROADWAY" and not ALLEY_RE.match(b.get("Name", ""))
    }

    # Section area indexed by UID_SUniqueID, restricted to included branches
    sections = mdb_csv(mdb, "Section")
    section_area: dict[str, float] = {}
    for s in sections:
        if s.get("UID_SBUniqueID") not in included_branches:
            continue
        length = to_float(s.get("SYS_Length")) or 0.0
        width = to_float(s.get("SYS_Width")) or 0.0
        adj = to_float(s.get("SYS_Area Adjustment")) or 0.0
        area = length * width + adj
        if area > 0:
            section_area[s["UID_SUniqueID"]] = area

    # Inspection date by UID_InspUniqueID
    inspections = mdb_csv(mdb, "Inspections")
    insp_date: dict[str, datetime] = {}
    for row in inspections:
        d = parse_date(row.get("DATE", ""))
        if d is not None:
            insp_date[row["UID_InspUniqueID"]] = d

    # Conditions → PCI samples: (date, pci, area, section_uid)
    conditions = mdb_csv(mdb, "Conditions")
    samples: list[Sample] = []
    for c in conditions:
        if c.get("UID_CMeasureUniqueID") != "PCI":
            continue
        sec_uid = c.get("UID_CSUniqueID")
        area = section_area.get(sec_uid)
        if area is None:
            continue
        insp_uid = c.get("UID_CINSPUniqueID")
        d = insp_date.get(insp_uid)
        if d is None:
            continue
        pci = to_float(c.get("Condition"))
        if pci is None:
            continue
        samples.append((d, pci, area, sec_uid))

    return cluster_surveys(samples, total_sections=len(section_area))


def cluster_surveys(samples: list[Sample], total_sections: int) -> list[dict]:
    """Bucket inspection samples into fiscal years (July 1 → June 30) and compute
    weighted-mean PCI per FY. Label by FY ending calendar year (FY 2015-16 → 2016).
    Drop any FY with coverage < MIN_COVERAGE_FRACTION or avg PCI ≥ MAX_SURVEY_AVG_PCI.
    """
    if not samples or total_sections <= 0:
        return []

    buckets: dict[int, list[Sample]] = {}
    for s in samples:
        fy_start = s[0].year if s[0].month >= 7 else s[0].year - 1
        buckets.setdefault(fy_start, []).append(s)

    min_sections = max(1, int(total_sections * MIN_COVERAGE_FRACTION))
    surveys = []
    for fy_start in sorted(buckets):
        c = buckets[fy_start]
        unique_sections = len({s[3] for s in c})
        if unique_sections < min_sections:
            continue
        num = sum(pci * area for _, pci, area, _ in c)
        den = sum(area for _, _, area, _ in c)
        if den <= 0:
            continue
        pci_mean = num / den
        # A survey whose weighted-mean PCI is ≥ 99 is a bulk-import placeholder
        # (every section stamped 100). Individual sections at 100 after a repair
        # are fine — this filter is on the *FY average*, not individual values.
        if pci_mean >= MAX_SURVEY_AVG_PCI:
            continue
        c.sort(key=lambda x: x[0])
        surveys.append(
            {
                "year": fy_start + 1,  # FY 15-16 → 2016
                "pci": round(pci_mean, 1),
                "sections": unique_sections,
                "coverage": round(unique_sections / total_sections, 2),
                "start": c[0][0].date().isoformat(),
                "end": c[-1][0].date().isoformat(),
            }
        )
    return surveys


def extract_sjc(hist_xlsx: Path, sections_xlsx: Path) -> list[dict]:
    """SJC: Sections.xlsx has Area per (Street ID, Section ID);
    Historical PCI xlsx has (Branch ID, Section ID, Date, PCI).
    Join on (Street ID == Branch ID, Section ID) and exclude parking lots /
    branches named 'ALLEY …' (neither present in current data, but guarded)."""
    sec_wb = openpyxl.load_workbook(sections_xlsx, data_only=True)
    sec_ws = sec_wb.active
    section_area: dict[tuple[str, str], float] = {}
    for r in sec_ws.iter_rows(min_row=2, values_only=True):
        street_id, section_id, street_name = str(r[0] or ""), str(r[1] or ""), str(r[2] or "")
        if not street_id or not section_id:
            continue
        if r[26] is not None:  # Parking Lot Type populated
            continue
        if ALLEY_RE.match(street_name):
            continue
        area = to_float(str(r[11])) if r[11] is not None else None
        if area is None or area <= 0:
            continue
        section_area[(street_id, section_id)] = area

    hist_wb = openpyxl.load_workbook(hist_xlsx, data_only=True)
    hist_ws = hist_wb.active
    samples: list[Sample] = []
    for row in hist_ws.iter_rows(min_row=2, values_only=True):
        if not row or row[2] is None or row[3] is None:
            continue
        branch_id, section_id = str(row[0] or ""), str(row[1] or "")
        key = (branch_id, section_id)
        area = section_area.get(key)
        if area is None:
            continue
        raw_date = row[2]
        if isinstance(raw_date, datetime):
            d = raw_date
        else:
            d = parse_date(str(raw_date))
        if d is None:
            continue
        pci = to_float(str(row[3]))
        if pci is None:
            continue
        samples.append((d, pci, area, f"{branch_id}-{section_id}"))
    return cluster_surveys(samples, total_sections=len(section_area))


def main() -> None:
    history: dict[str, list[dict]] = {}
    for city, filename in MICROPAVER_CITIES:
        mdb = PMP_DIR / filename
        print(f"  {city}: extracting from {filename} ...", flush=True)
        surveys = extract_micropaver(mdb)
        print(f"    {len(surveys)} surveys: {[s['year'] for s in surveys]}")
        history[city] = surveys

    print(f"  San Juan Capistrano: extracting from {SJC_HIST_XLSX} + {SJC_SECTIONS_XLSX} ...", flush=True)
    sjc_surveys = extract_sjc(PMP_DIR / SJC_HIST_XLSX, PMP_DIR / SJC_SECTIONS_XLSX)
    print(f"    {len(sjc_surveys)} surveys: {[s['year'] for s in sjc_surveys]}")
    history["San Juan Capistrano"] = sjc_surveys

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(history, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
