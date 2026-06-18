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


from .xlsx_reader import num_to_col

_ROW_GROUPS = [["A", "B", "C", "D"], ["E", "F", "G", "H"], ["I", "J", "K", "L"]]


def _cell(cells, col_num, row):
    c = cells.get(f"{num_to_col(col_num)}{row}")
    return c["value"] if c else None


def extract_entrants(entries_cells: dict, roster: dict) -> list:
    entrants = []
    for block in range(60):  # generous upper bound; stop on an empty block
        name_row = 1 + 17 * block
        found = False
        for k in range(3):
            base = 1 + 17 * k
            name = _cell(entries_cells, base + 1, name_row)
            if not name:
                continue
            found = True
            multipliers = {}
            for rg_idx, groups in enumerate(_ROW_GROUPS):
                for q, g in enumerate(groups):
                    for slot in range(4):
                        team_row = name_row + 2 + rg_idx * 5 + slot
                        mult = _cell(entries_cells, base + 4 * q + 2, team_row)
                        canonical = roster[g][slot]
                        multipliers[canonical] = (
                            int(float(mult)) if mult not in (None, "") else 0)
            stars = [t for t, m in multipliers.items() if m == 5]
            if len(stars) != 1:
                raise ValueError(f"{name!r}: expected exactly one x5 star, got {stars}")
            entrants.append({
                "name": name.strip(),
                "starred_team": stars[0],
                "multipliers": multipliers,
            })
        if not found:
            break
    return entrants
