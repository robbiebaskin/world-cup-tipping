# wc_scorer/extract.py
"""Extract committed JSON reference data from the tipping workbook."""
import re
from .xlsx_reader import cell, col_to_num


def extract_roster(results_cells: dict) -> dict:
    """Scan column A of the Results tab: 'Group X' headers each followed by 4 teams."""
    roster = {}
    current = None
    for row in range(1, 80):
        a = cell(results_cells, "A", row)
        if not a:
            continue
        a = a.strip()
        m = re.match(r"Group ([A-L])$", a)
        if m:
            current = m.group(1)
            roster[current] = []
        elif current and len(roster[current]) < 4:
            roster[current].append(a)
    return roster
