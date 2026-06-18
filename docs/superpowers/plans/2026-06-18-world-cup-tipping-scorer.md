# World Cup 2026 Tipping Scorer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that pulls live 2026 World Cup results from ESPN and reproduces the tipping workbook's scoring exactly, outputting the ladder and a per-country breakdown of every entrant's score.

**Architecture:** A one-off `extract` command parses the `.xlsx` into committed JSON reference files (roster, entrants, ESPN→roster name map); the `score` command reads only those JSON files plus the cached ESPN feed, derives each team's stats/points, applies each entrant's rank multipliers, and renders the ladder + per-country breakdowns. Two clear layers: team performance points, then per-entrant multiplied scores.

**Tech Stack:** Python 3 standard library only — `zipfile`/`re` (xlsx parsing), `urllib`/`json` (ESPN feed), `unittest` (tests), `argparse`/`csv` (CLI/output). No pip installs (openpyxl/pytest are unavailable/broken in this environment).

## Global Constraints

- **Standard library only.** No third-party packages. openpyxl fails (expat broken); pytest may be absent — use `unittest`.
- **Run all commands from the repo root** `/Users/robbiebaskin/Documents/personal/dev/drez` so `from wc_scorer import ...` resolves.
- **Canonical team names come from `roster.json`** (extracted from the workbook), e.g. `Korea Rep.`, `Turkey`, `Congo`, `Uzebekistan`. Never hand-type team data.
- **The ⭐ star = the team an entrant rated with multiplier `5` in the grid.** Never read it from `Ladder!C` ("* Selected"), which is hand-typed and contains at least one error.
- **63 entrants; 48 teams in 12 groups of 4.** These are invariants the extractor must assert.
- **Score only completed matches** (`status.type.completed == true`).
- **Scoring weights (verbatim from `Results!O` formula):** win 5, draw 3 (incl. penalty games), loss 0, goals-for 2, goals-against −1, yellow −1, red −5, group-winner 5, qualify 2, QF 10, SF 15, final 20, winner 30.
- **ESPN endpoint:** `https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=<START-END>&limit=300`. Default range `20260611-20260719`. Cache every fetch to disk.
- **Commit after every task.**

---

### Task 1: Project scaffold

**Files:**
- Create: `wc_scorer/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `.gitignore`
- Create: `tests/test_sanity.py`
- Copy: `World Cup Tipping 2026.xlsx` from `~/Downloads` into repo root
- Create: `data/reference/.gitkeep`, `data/cache/.gitkeep`, `out/.gitkeep`

**Interfaces:**
- Produces: the package/test layout every later task imports from.

- [ ] **Step 1: Initialize git and directory structure**

```bash
cd /Users/robbiebaskin/Documents/personal/dev/drez
git init
mkdir -p wc_scorer tests data/reference data/cache out
touch wc_scorer/__init__.py tests/__init__.py data/reference/.gitkeep data/cache/.gitkeep out/.gitkeep
cp "/Users/robbiebaskin/Downloads/World Cup Tipping 2026.xlsx" "World Cup Tipping 2026.xlsx"
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
__pycache__/
*.pyc
data/cache/*.json
out/*.csv
out/*.md
.DS_Store
```

- [ ] **Step 3: Write a sanity test**

```python
# tests/test_sanity.py
import unittest, os

class TestSanity(unittest.TestCase):
    def test_workbook_present(self):
        self.assertTrue(os.path.exists("World Cup Tipping 2026.xlsx"))

    def test_package_importable(self):
        import wc_scorer  # noqa: F401

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 4: Run the sanity test**

Run: `python3 -m unittest tests.test_sanity -v`
Expected: PASS (2 tests OK).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: scaffold wc_scorer package, tests, and workbook"
```

---

### Task 2: `xlsx_reader.py` — self-closing-cell-safe cell reader

**Files:**
- Create: `wc_scorer/xlsx_reader.py`
- Create: `tests/test_xlsx_reader.py`

**Interfaces:**
- Produces:
  - `col_to_num(col: str) -> int` ("A"→1, "AA"→27)
  - `num_to_col(n: int) -> str` (1→"A")
  - `read_sheet(xlsx_path: str, sheet_name: str) -> dict[str, dict]` mapping cell ref → `{"value": str|None, "formula": str|None}`
  - `cell(cells: dict, col: str, row: int) -> str|None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_xlsx_reader.py
import unittest
from wc_scorer.xlsx_reader import col_to_num, num_to_col, read_sheet, cell

XLSX = "World Cup Tipping 2026.xlsx"

class TestColumns(unittest.TestCase):
    def test_col_round_trip(self):
        for n in (1, 16, 17, 18, 26, 27, 35, 50):
            self.assertEqual(col_to_num(num_to_col(n)), n)
        self.assertEqual(num_to_col(1), "A")
        self.assertEqual(num_to_col(18), "R")
        self.assertEqual(num_to_col(35), "AI")

class TestReadSheet(unittest.TestCase):
    def setUp(self):
        self.results = read_sheet(XLSX, "Results")

    def test_group_header_and_first_team_present(self):
        # The first team of each group lives on the SAME row as the points
        # formula; a reader that mishandles self-closing cells drops it.
        self.assertEqual(cell(self.results, "A", 2), "Group A")
        self.assertEqual(cell(self.results, "A", 3), "Mexico")
        self.assertEqual(cell(self.results, "A", 4), "South Africa")

    def test_points_formula_captured(self):
        f = self.results["O3"]["formula"]
        self.assertIn("(B3*5)", f)
        self.assertIn("(N3*30)", f)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_xlsx_reader -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'wc_scorer.xlsx_reader'`.

- [ ] **Step 3: Write the implementation**

```python
# wc_scorer/xlsx_reader.py
"""Minimal, dependency-free .xlsx reader (openpyxl/expat are unavailable here).

An .xlsx is a zip of XML. We resolve shared strings and read cell values and
formulas with regex. Critically, Excel writes EMPTY cells as self-closing tags
(<c r=".." />); a regex that assumes every <c> has a </c> swallows following
cells, so we match both forms.
"""
import zipfile
import re
import html

_NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def col_to_num(col: str) -> int:
    n = 0
    for c in col:
        n = n * 26 + (ord(c) - 64)
    return n


def num_to_col(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _shared_strings(z: zipfile.ZipFile) -> list:
    try:
        xml = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
    except KeyError:
        return []
    out = []
    for si in re.findall(r"<si>(.*?)</si>", xml, re.S):
        out.append(html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
    return out


def _sheet_path(z: zipfile.ZipFile, sheet_name: str) -> str:
    wb = z.read("xl/workbook.xml").decode("utf-8", "replace")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "replace")
    rid_target = dict(re.findall(
        r'<Relationship[^>]*?Id="([^"]*)"[^>]*?Target="([^"]*)"', rels))
    for m in re.finditer(r'<sheet[^>]*?name="([^"]*)"[^>]*?r:id="([^"]*)"', wb):
        if m.group(1) == sheet_name:
            target = rid_target[m.group(2)].lstrip("/")
            return target if target.startswith("xl/") else "xl/" + target
    raise KeyError(f"sheet not found: {sheet_name}")


def read_sheet(xlsx_path: str, sheet_name: str) -> dict:
    z = zipfile.ZipFile(xlsx_path)
    ss = _shared_strings(z)
    xml = z.read(_sheet_path(z, sheet_name)).decode("utf-8", "replace")
    cells = {}
    for c in re.finditer(r"<c\b([^>]*?)(?:/>|>(.*?)</c>)", xml, re.S):
        attrs, body = c.group(1), c.group(2)
        rm = re.search(r'\br="([A-Z]+\d+)"', attrs)
        if not rm:
            continue
        tm = re.search(r'\bt="([^"]*)"', attrs)
        t = tm.group(1) if tm else None
        value = formula = None
        if body:
            fm = re.search(r"<f[^>]*>(.*?)</f>", body, re.S)
            formula = html.unescape(fm.group(1)) if fm else None
            vm = re.search(r"<v[^>]*>(.*?)</v>", body, re.S)
            value = vm.group(1) if vm else None
        if t == "s" and value is not None:
            value = ss[int(value)]
        elif value is not None:
            value = html.unescape(value)
        cells[rm.group(1)] = {"value": value, "formula": formula}
    return cells


def cell(cells: dict, col: str, row: int):
    c = cells.get(f"{col}{row}")
    return c["value"] if c else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_xlsx_reader -v`
Expected: PASS (all tests OK).

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/xlsx_reader.py tests/test_xlsx_reader.py
git commit -m "feat: add self-closing-cell-safe xlsx reader"
```

---

### Task 3: Roster extraction

**Files:**
- Create: `wc_scorer/extract.py`
- Create: `tests/test_extract_roster.py`

**Interfaces:**
- Consumes: `read_sheet`, `cell`, `col_to_num` from `wc_scorer.xlsx_reader`.
- Produces: `extract_roster(results_cells: dict) -> dict[str, list[str]]` — group letter → 4 team names in order.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract_roster.py
import unittest
from wc_scorer.xlsx_reader import read_sheet
from wc_scorer.extract import extract_roster

class TestRoster(unittest.TestCase):
    def setUp(self):
        self.roster = extract_roster(read_sheet("World Cup Tipping 2026.xlsx", "Results"))

    def test_twelve_groups_of_four(self):
        self.assertEqual(sorted(self.roster), list("ABCDEFGHIJKL"))
        for g, teams in self.roster.items():
            self.assertEqual(len(teams), 4, g)

    def test_48_unique_teams(self):
        flat = [t for ts in self.roster.values() for t in ts]
        self.assertEqual(len(flat), 48)
        self.assertEqual(len(set(flat)), 48)

    def test_known_members(self):
        self.assertEqual(self.roster["A"], ["Mexico", "South Africa", "Korea Rep.", "Czechia"])
        self.assertIn("Uzebekistan", self.roster["K"])  # workbook's spelling

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_extract_roster -v`
Expected: FAIL with `cannot import name 'extract_roster'`.

- [ ] **Step 3: Write the implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_extract_roster -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/extract.py tests/test_extract_roster.py
git commit -m "feat: extract 12x4 team roster from Results tab"
```

---

### Task 4: Entrant extraction

**Files:**
- Modify: `wc_scorer/extract.py` (add `extract_entrants`)
- Create: `tests/test_extract_entrants.py`

**Interfaces:**
- Consumes: `extract_roster`, `read_sheet`.
- Produces: `extract_entrants(entries_cells: dict, roster: dict) -> list[dict]` where each entrant is `{"name": str, "starred_team": str, "multipliers": dict[str, int]}` (multipliers cover all 48 teams; 0 = unranked).

**Verified geometry:** name rows at `1 + 17*block`; three entrant bands at base columns `1 + 17*k` (k=0,1,2 → A, R, AI); within a band, three row-groups at offsets +2, +7, +12 from the name row, each holding 4 group-quadrants of 4 teams; quadrant `q` (0–3): team col `base + 4*q`, multiplier col `base + 4*q + 2`; the three row-groups map to group letters `[A,B,C,D]`, `[E,F,G,H]`, `[I,J,K,L]`. Multipliers join to teams positionally against the roster.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract_entrants.py
import unittest
from wc_scorer.xlsx_reader import read_sheet
from wc_scorer.extract import extract_roster, extract_entrants

class TestEntrants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        xlsx = "World Cup Tipping 2026.xlsx"
        roster = extract_roster(read_sheet(xlsx, "Results"))
        cls.entrants = extract_entrants(read_sheet(xlsx, "Entries"), roster)
        cls.by_name = {e["name"]: e for e in cls.entrants}

    def test_count(self):
        self.assertEqual(len(self.entrants), 63)

    def test_each_has_one_star_and_48_multipliers(self):
        for e in self.entrants:
            stars = [t for t, m in e["multipliers"].items() if m == 5]
            self.assertEqual(len(stars), 1, e["name"])
            self.assertEqual(e["starred_team"], stars[0], e["name"])
            self.assertEqual(len(e["multipliers"]), 48, e["name"])

    def test_known_entrants(self):
        # From the workbook grid (NOT the hand-typed Ladder label).
        self.assertEqual(self.by_name["Lennon Dresner (P)"]["starred_team"], "Brazil")
        # Luka's grid stars France at x5 even though Ladder!C says "Spain".
        self.assertEqual(self.by_name["Luka Obradovic"]["starred_team"], "France")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_extract_entrants -v`
Expected: FAIL with `cannot import name 'extract_entrants'`.

- [ ] **Step 3: Write the implementation (append to `wc_scorer/extract.py`)**

```python
# append to wc_scorer/extract.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_extract_entrants -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/extract.py tests/test_extract_entrants.py
git commit -m "feat: extract 63 entrants and rank multipliers from Entries tab"
```

---

### Task 5: ESPN feed — fetch (cached) + team names

**Files:**
- Create: `wc_scorer/espn.py`
- Create: `tests/test_espn_fetch.py`

**Interfaces:**
- Produces:
  - `DEFAULT_DATES = "20260611-20260719"`
  - `fetch(dates: str = DEFAULT_DATES, cache_dir: str = "data/cache", refresh: bool = False) -> dict`
  - `team_names(raw: dict) -> set[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_espn_fetch.py
import unittest, os, json
from wc_scorer import espn

class TestFetch(unittest.TestCase):
    def test_fetch_caches_and_reads_back(self):
        raw = espn.fetch(cache_dir="data/cache")            # network or cache
        self.assertIn("events", raw)
        self.assertTrue(len(raw["events"]) >= 20)
        cached = [f for f in os.listdir("data/cache") if f.endswith(".json")]
        self.assertTrue(cached, "expected a cache file to be written")
        raw2 = espn.fetch(cache_dir="data/cache", refresh=False)  # from cache
        self.assertEqual(len(raw["events"]), len(raw2["events"]))

    def test_team_names_includes_real_and_placeholders(self):
        raw = espn.fetch(cache_dir="data/cache")
        names = espn.team_names(raw)
        self.assertIn("Mexico", names)
        self.assertIn("South Korea", names)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_espn_fetch -v`
Expected: FAIL with `No module named 'wc_scorer.espn'`.

- [ ] **Step 3: Write the implementation**

```python
# wc_scorer/espn.py
"""Fetch and parse the unofficial ESPN FIFA World Cup scoreboard feed."""
import json
import os
import subprocess
import urllib.request

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
DEFAULT_DATES = "20260611-20260719"


def _url(dates: str) -> str:
    return f"{BASE}?dates={dates}&limit=300"


def _http_get(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read()
    except Exception:
        # macOS Homebrew Python can lack CA certs; curl is verified to work here.
        return subprocess.check_output(["curl", "-s", url], timeout=30)


def fetch(dates: str = DEFAULT_DATES, cache_dir: str = "data/cache",
          refresh: bool = False) -> dict:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"espn-{dates}.json")
    if refresh or not os.path.exists(path):
        data = _http_get(_url(dates))
        with open(path, "wb") as f:
            f.write(data)
    with open(path, "rb") as f:
        return json.load(f)


def team_names(raw: dict) -> set:
    names = set()
    for event in raw.get("events", []):
        for comp in event.get("competitions", []):
            for c in comp.get("competitors", []):
                dn = c.get("team", {}).get("displayName")
                if dn:
                    names.add(dn)
    return names
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_espn_fetch -v`
Expected: PASS (writes `data/cache/espn-20260611-20260719.json`).

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/espn.py tests/test_espn_fetch.py
git commit -m "feat: fetch and cache ESPN feed; extract team names"
```

---

### Task 6: ESPN→roster name map builder

**Files:**
- Modify: `wc_scorer/extract.py` (add `norm`, `build_name_map`)
- Create: `tests/test_name_map.py`

**Interfaces:**
- Consumes: `extract_roster`, `espn.team_names`.
- Produces:
  - `norm(s: str) -> str` (accent/case/punctuation-stripped key)
  - `build_name_map(roster: dict, espn_names) -> tuple[dict, list]` returns `(name_map, exceptions)`. `name_map` maps every resolvable ESPN name → canonical; `exceptions` lists real ESPN team names that need a manual alias. Knockout placeholders are filtered from both.

**Verified:** 42 of 50 feed names auto-match; the 6 real aliases are `South Korea→Korea Rep.`, `Türkiye→Turkey`, `United States→USA`, `Congo DR→Congo`, `Bosnia-Herzegovina→Bosnia`, `Uzbekistan→Uzebekistan`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_name_map.py
import unittest
from wc_scorer.xlsx_reader import read_sheet
from wc_scorer.extract import extract_roster, build_name_map, norm

ALIASES = {
    "South Korea": "Korea Rep.", "Türkiye": "Turkey", "United States": "USA",
    "Congo DR": "Congo", "Bosnia-Herzegovina": "Bosnia", "Uzbekistan": "Uzebekistan",
}

class TestNameMap(unittest.TestCase):
    def setUp(self):
        self.roster = extract_roster(read_sheet("World Cup Tipping 2026.xlsx", "Results"))

    def test_norm_strips_accents_and_punct(self):
        self.assertEqual(norm("Curaçao"), norm("Curacao"))
        self.assertEqual(norm("Korea Rep."), "korearep")

    def test_auto_matches_and_aliases(self):
        feed = {"Mexico", "Curaçao", "South Korea", "Türkiye", "United States",
                "Congo DR", "Bosnia-Herzegovina", "Uzbekistan",
                "Group A 2nd Place", "Winner Match 73"}
        name_map, exceptions = build_name_map(self.roster, feed,
                                              manual_aliases=ALIASES)
        self.assertEqual(name_map["Mexico"], "Mexico")
        self.assertEqual(name_map["Curaçao"], "Curacao")
        self.assertEqual(name_map["South Korea"], "Korea Rep.")
        self.assertNotIn("Group A 2nd Place", name_map)   # placeholder filtered
        self.assertEqual(exceptions, [])                  # all resolved via aliases

    def test_unaliased_real_team_becomes_exception(self):
        name_map, exceptions = build_name_map(self.roster, {"South Korea"},
                                              manual_aliases={})
        self.assertIn("South Korea", exceptions)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_name_map -v`
Expected: FAIL with `cannot import name 'build_name_map'`.

- [ ] **Step 3: Write the implementation (append to `wc_scorer/extract.py`)**

```python
# append to wc_scorer/extract.py
import unicodedata

# ESPN names for not-yet-played knockout fixtures, not real teams.
_PLACEHOLDER_RE = re.compile(r"(\d+(st|nd|rd|th)?\s+place|winner|runner|loser|"
                             r"group [a-l]\b.*place|match \d+)", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def build_name_map(roster: dict, espn_names, manual_aliases: dict = None):
    manual_aliases = manual_aliases or {}
    canon = [t for ts in roster.values() for t in ts]
    by_norm = {norm(t): t for t in canon}
    name_map, exceptions = {}, []
    for name in sorted(espn_names):
        if _PLACEHOLDER_RE.search(name):
            continue
        if name in canon:
            name_map[name] = name
        elif name in manual_aliases:
            name_map[name] = manual_aliases[name]
        elif norm(name) in by_norm:
            name_map[name] = by_norm[norm(name)]
        else:
            exceptions.append(name)
    return name_map, exceptions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_name_map -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/extract.py tests/test_name_map.py
git commit -m "feat: generate ESPN->roster name map with placeholder filtering"
```

---

### Task 7: `extract` command — write reference JSON + validate

**Files:**
- Modify: `wc_scorer/extract.py` (add `MANUAL_ALIASES`, `extract`)
- Create: `tests/test_extract_run.py`

**Interfaces:**
- Consumes: `extract_roster`, `extract_entrants`, `build_name_map`, `espn.fetch`, `espn.team_names`.
- Produces: `extract(xlsx_path: str, out_dir: str = "data/reference", espn_names=None, now: str = "") -> dict` — writes `roster.json`, `entrants.json`, `name_map.json`, and (if any) `name_map_exceptions.json`; returns a summary dict `{"roster": N, "entrants": N, "name_map": N, "exceptions": [...]}`. Raises `ValueError` on invariant failure.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract_run.py
import unittest, os, json, tempfile
from wc_scorer import espn
from wc_scorer.extract import extract

class TestExtractRun(unittest.TestCase):
    def test_writes_valid_reference_files(self):
        names = espn.team_names(espn.fetch(cache_dir="data/cache"))
        with tempfile.TemporaryDirectory() as d:
            summary = extract("World Cup Tipping 2026.xlsx", out_dir=d,
                              espn_names=names, now="2026-06-18T00:00:00")
            roster = json.load(open(os.path.join(d, "roster.json")))
            entrants = json.load(open(os.path.join(d, "entrants.json")))
            name_map = json.load(open(os.path.join(d, "name_map.json")))
            self.assertEqual(len([t for g in roster["groups"].values() for t in g]), 48)
            self.assertEqual(len(entrants["entrants"]), 63)
            self.assertEqual(name_map["map"]["South Korea"], "Korea Rep.")
            self.assertEqual(summary["exceptions"], [])  # all feed names resolved
            self.assertIn("_meta", roster)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_extract_run -v`
Expected: FAIL with `cannot import name 'extract'`.

- [ ] **Step 3: Write the implementation (append to `wc_scorer/extract.py`)**

```python
# append to wc_scorer/extract.py
import json
import os
from .xlsx_reader import read_sheet

MANUAL_ALIASES = {
    "South Korea": "Korea Rep.",
    "Türkiye": "Turkey",
    "United States": "USA",
    "Congo DR": "Congo",
    "Bosnia-Herzegovina": "Bosnia",
    "Uzbekistan": "Uzebekistan",
}


def _meta(source: str, now: str) -> dict:
    return {"source": source, "extracted_at": now}


def _write(path: str, obj: dict):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def extract(xlsx_path: str, out_dir: str = "data/reference",
            espn_names=None, now: str = "") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    roster = extract_roster(read_sheet(xlsx_path, "Results"))
    entrants = extract_entrants(read_sheet(xlsx_path, "Entries"), roster)

    flat = [t for ts in roster.values() for t in ts]
    if len(roster) != 12 or len(flat) != 48 or len(set(flat)) != 48:
        raise ValueError(f"roster invariant failed: {len(roster)} groups, {len(flat)} teams")
    if len(entrants) != 63:
        raise ValueError(f"expected 63 entrants, got {len(entrants)}")
    for e in entrants:
        if len(e["multipliers"]) != 48:
            raise ValueError(f"{e['name']}: {len(e['multipliers'])} multipliers")

    name_map, exceptions = build_name_map(roster, espn_names or [],
                                          manual_aliases=MANUAL_ALIASES)

    _write(os.path.join(out_dir, "roster.json"),
           {"_meta": _meta(xlsx_path, now), "groups": roster})
    _write(os.path.join(out_dir, "entrants.json"),
           {"_meta": _meta(xlsx_path, now), "entrants": entrants})
    _write(os.path.join(out_dir, "name_map.json"),
           {"_meta": _meta(xlsx_path, now), "map": name_map})
    if exceptions:
        _write(os.path.join(out_dir, "name_map_exceptions.json"),
               {"_meta": _meta(xlsx_path, now), "exceptions": exceptions})

    return {"roster": len(flat), "entrants": len(entrants),
            "name_map": len(name_map), "exceptions": exceptions}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_extract_run -v`
Expected: PASS.

- [ ] **Step 5: Generate the real reference files and commit them**

```bash
python3 -c "from wc_scorer import espn, extract; \
n=espn.team_names(espn.fetch()); \
print(extract.extract('World Cup Tipping 2026.xlsx', espn_names=n, now='2026-06-18T00:00:00'))"
git add wc_scorer/extract.py tests/test_extract_run.py data/reference/roster.json data/reference/entrants.json data/reference/name_map.json
git commit -m "feat: extract command writes validated reference JSON"
```

---

### Task 8: Reference loaders (`teams.py`, `rankings.py`)

**Files:**
- Create: `wc_scorer/teams.py`
- Create: `wc_scorer/rankings.py`
- Create: `tests/test_loaders.py`

**Interfaces:**
- Produces:
  - `teams.load_roster(ref_dir="data/reference") -> dict[str, list[str]]` (group→teams)
  - `teams.team_group(roster) -> dict[str, str]` (team→group letter)
  - `teams.load_name_map(ref_dir="data/reference") -> dict[str, str]`
  - `teams.to_canonical(name: str, name_map: dict) -> str` (raises `KeyError` if absent)
  - `rankings.load_entrants(ref_dir="data/reference") -> list[dict]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_loaders.py
import unittest
from wc_scorer import teams, rankings

class TestLoaders(unittest.TestCase):
    def test_roster_and_groups(self):
        roster = teams.load_roster()
        self.assertEqual(len(roster), 12)
        tg = teams.team_group(roster)
        self.assertEqual(tg["Mexico"], "A")

    def test_to_canonical(self):
        nm = teams.load_name_map()
        self.assertEqual(teams.to_canonical("South Korea", nm), "Korea Rep.")
        self.assertEqual(teams.to_canonical("Mexico", nm), "Mexico")
        with self.assertRaises(KeyError):
            teams.to_canonical("Atlantis", nm)

    def test_entrants(self):
        es = rankings.load_entrants()
        self.assertEqual(len(es), 63)
        self.assertTrue(all("multipliers" in e for e in es))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_loaders -v`
Expected: FAIL with `No module named 'wc_scorer.teams'`.

- [ ] **Step 3: Write the implementations**

```python
# wc_scorer/teams.py
import json
import os


def load_roster(ref_dir: str = "data/reference") -> dict:
    with open(os.path.join(ref_dir, "roster.json")) as f:
        return json.load(f)["groups"]


def team_group(roster: dict) -> dict:
    return {t: g for g, ts in roster.items() for t in ts}


def load_name_map(ref_dir: str = "data/reference") -> dict:
    with open(os.path.join(ref_dir, "name_map.json")) as f:
        return json.load(f)["map"]


def to_canonical(name: str, name_map: dict) -> str:
    if name not in name_map:
        raise KeyError(f"unmapped ESPN team name: {name!r}")
    return name_map[name]
```

```python
# wc_scorer/rankings.py
import json
import os


def load_entrants(ref_dir: str = "data/reference") -> list:
    with open(os.path.join(ref_dir, "entrants.json")) as f:
        return json.load(f)["entrants"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_loaders -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/teams.py wc_scorer/rankings.py tests/test_loaders.py
git commit -m "feat: add roster/name-map/entrants loaders"
```

---

### Task 9: ESPN feed — parse matches

**Files:**
- Modify: `wc_scorer/espn.py` (add `stage_of`, `parse`)
- Create: `tests/test_espn_parse.py`

**Interfaces:**
- Consumes: `teams.to_canonical`, `teams.load_name_map`, `teams.load_roster`.
- Produces:
  - `stage_of(event: dict) -> str` ∈ {"group","r32","r16","qf","sf","final","third","other"}
  - `parse(raw: dict, name_map: dict) -> list[dict]`; each match: `{"stage","team_a","team_b","ga","gb","completed","penalties","shootout_winner","cards": {team:{"yellow":int,"red":int}}}` (team names canonical). Only real-team matches are returned (placeholder fixtures skipped).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_espn_parse.py
import unittest
from wc_scorer import espn, teams

class TestParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = espn.fetch(cache_dir="data/cache")
        cls.matches = espn.parse(raw, teams.load_name_map())

    def test_completed_group_matches_parsed(self):
        done = [m for m in self.matches if m["completed"]]
        self.assertGreaterEqual(len(done), 20)
        opener = next(m for m in done if {m["team_a"], m["team_b"]} == {"Mexico", "South Africa"})
        self.assertEqual(opener["stage"], "group")
        # Mexico 2 - 0 South Africa
        gf = opener["ga"] if opener["team_a"] == "Mexico" else opener["gb"]
        self.assertEqual(gf, 2)

    def test_names_are_canonical(self):
        for m in self.matches:
            self.assertNotIn("South Korea", (m["team_a"], m["team_b"]))

    def test_stage_helper(self):
        self.assertEqual(espn.stage_of({"season": {"slug": "group-stage"}}), "group")
        self.assertEqual(espn.stage_of({"season": {"slug": "round-of-32"}}), "r32")
        self.assertEqual(espn.stage_of({"season": {"slug": "quarterfinals"}}), "qf")
        self.assertEqual(espn.stage_of({"season": {"slug": "final"}}), "final")

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_espn_parse -v`
Expected: FAIL with `cannot import name ... 'stage_of'` / `'parse'`.

- [ ] **Step 3: Write the implementation (append to `wc_scorer/espn.py`)**

```python
# append to wc_scorer/espn.py
import re as _re
from .teams import to_canonical


def stage_of(event: dict) -> str:
    text = (event.get("season", {}).get("slug", "") or "").lower()
    for comp in event.get("competitions", []):
        for note in comp.get("notes", []) or []:
            text += " " + (note.get("headline", "") or "").lower()
    if _re.search(r"third|3rd", text):
        return "third"
    if "32" in text:
        return "r32"
    if "16" in text:
        return "r16"
    if "quarter" in text:
        return "qf"
    if "semi" in text:
        return "sf"
    if "group" in text:
        return "group"
    if "final" in text:
        return "final"
    return "other"


def _int(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def parse(raw: dict, name_map: dict) -> list:
    matches = []
    for event in raw.get("events", []):
        stage = stage_of(event)
        for comp in event.get("competitions", []):
            cs = comp.get("competitors", [])
            if len(cs) != 2:
                continue
            try:
                names = [to_canonical(c["team"]["displayName"], name_map) for c in cs]
            except KeyError:
                # Skip placeholder/TBD fixtures (not-yet-played knockouts).
                continue
            id_to_team = {c.get("team", {}).get("id"): n for c, n in zip(cs, names)}
            goals = [_int(c.get("score")) for c in cs]
            shootout = [c.get("shootoutScore") for c in cs]
            completed = bool(comp.get("status", {}).get("type", {}).get("completed"))
            penalties = all(s not in (None, "") for s in shootout)
            shootout_winner = None
            if penalties:
                hi = 0 if _int(shootout[0]) >= _int(shootout[1]) else 1
                shootout_winner = names[hi]
            cards = {n: {"yellow": 0, "red": 0} for n in names}
            for d in comp.get("details", []) or []:
                ttext = (d.get("type", {}).get("text") or "").lower()
                tid = d.get("team", {}).get("id")
                team = id_to_team.get(tid)
                if not team:
                    continue
                if "yellow" in ttext and "red" in ttext:   # second yellow
                    cards[team]["yellow"] += 1
                    cards[team]["red"] += 1
                elif "yellow" in ttext:
                    cards[team]["yellow"] += 1
                elif "red" in ttext:
                    cards[team]["red"] += 1
            matches.append({
                "stage": stage,
                "team_a": names[0], "team_b": names[1],
                "ga": goals[0], "gb": goals[1],
                "completed": completed,
                "penalties": penalties,
                "shootout_winner": shootout_winner,
                "cards": cards,
            })
    return matches
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_espn_parse -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/espn.py tests/test_espn_parse.py
git commit -m "feat: parse ESPN events into canonical match records"
```

---

### Task 10: Scoring — team stats derivation

**Files:**
- Create: `wc_scorer/scoring.py`
- Create: `tests/test_team_stats.py`

**Interfaces:**
- Consumes: parsed matches, `roster`.
- Produces:
  - `empty_stats() -> dict` with keys `win,draw,loss,gf,ga,yellow,red,group_winner,qualify,qf,sf,final,winner` (all 0).
  - `team_stats(matches: list, roster: dict, overrides: dict = None) -> dict[str, dict]` — every roster team → its stats. Includes a private list of group-winner tie warnings on the returned dict under key `"_warnings"`.

**Derivation rules:** accumulate W/D/L, GF, GA, cards over all completed matches (penalty KO = draw for both). Milestones: `qualify` if the team appears in an `r32` match; `qf`/`sf`/`final` if it appears in a match of that stage; `winner` if it wins the `final`. `group_winner` = top of each group's table (3-1-0, then GD, then GF) over completed group matches; a tie for top is recorded in `_warnings` and not auto-awarded. `overrides` may set `{"force_group_winner": {"A": "Mexico"}, "patch": {"Mexico": {"red": 1}}}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_team_stats.py
import unittest
from wc_scorer.scoring import team_stats, empty_stats

ROSTER = {"A": ["Mexico", "South Africa", "Korea Rep.", "Czechia"],
          "B": ["Canada", "Bosnia", "Qatar", "Switzerland"]}

def m(stage, a, b, ga, gb, completed=True, penalties=False, winner=None, cards=None):
    return {"stage": stage, "team_a": a, "team_b": b, "ga": ga, "gb": gb,
            "completed": completed, "penalties": penalties, "shootout_winner": winner,
            "cards": cards or {a: {"yellow": 0, "red": 0}, b: {"yellow": 0, "red": 0}}}

class TestTeamStats(unittest.TestCase):
    def test_win_draw_goals_cards(self):
        matches = [
            m("group", "Mexico", "South Africa", 2, 0,
              cards={"Mexico": {"yellow": 1, "red": 0}, "South Africa": {"yellow": 0, "red": 1}}),
            m("group", "Mexico", "Korea Rep.", 1, 1),
        ]
        s = team_stats(matches, ROSTER)
        self.assertEqual(s["Mexico"]["win"], 1)
        self.assertEqual(s["Mexico"]["draw"], 1)
        self.assertEqual(s["Mexico"]["gf"], 3)
        self.assertEqual(s["Mexico"]["ga"], 1)
        self.assertEqual(s["Mexico"]["yellow"], 1)
        self.assertEqual(s["South Africa"]["loss"], 1)
        self.assertEqual(s["South Africa"]["red"], 1)

    def test_group_winner(self):
        matches = [
            m("group", "Mexico", "South Africa", 3, 0),
            m("group", "Korea Rep.", "Czechia", 0, 0),
        ]
        s = team_stats(matches, ROSTER)
        self.assertEqual(s["Mexico"]["group_winner"], 1)
        self.assertEqual(s["South Africa"]["group_winner"], 0)

    def test_penalty_knockout_is_draw_for_both_winner_advances(self):
        matches = [m("r32", "Mexico", "Canada", 1, 1, penalties=True, winner="Mexico")]
        s = team_stats(matches, ROSTER)
        self.assertEqual(s["Mexico"]["draw"], 1)
        self.assertEqual(s["Canada"]["draw"], 1)
        self.assertEqual(s["Mexico"]["qualify"], 1)
        self.assertEqual(s["Canada"]["qualify"], 1)

    def test_override_group_winner(self):
        matches = [m("group", "Mexico", "South Africa", 3, 0)]
        s = team_stats(matches, ROSTER, overrides={"force_group_winner": {"A": "Korea Rep."}})
        self.assertEqual(s["Korea Rep."]["group_winner"], 1)
        self.assertEqual(s["Mexico"]["group_winner"], 0)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_team_stats -v`
Expected: FAIL with `No module named 'wc_scorer.scoring'`.

- [ ] **Step 3: Write the implementation**

```python
# wc_scorer/scoring.py
"""Layer 1 (team performance points) and Layer 2 (per-entrant scoring)."""

_STAT_KEYS = ["win", "draw", "loss", "gf", "ga", "yellow", "red",
              "group_winner", "qualify", "qf", "sf", "final", "winner"]
_STAGE_MILESTONE = {"r32": "qualify", "qf": "qf", "sf": "sf", "final": "final"}


def empty_stats() -> dict:
    return {k: 0 for k in _STAT_KEYS}


def _winner_of(match: dict):
    if match["penalties"]:
        return None  # scored as a draw; advancement handled separately
    if match["ga"] > match["gb"]:
        return match["team_a"]
    if match["gb"] > match["ga"]:
        return match["team_b"]
    return None


def team_stats(matches: list, roster: dict, overrides: dict = None) -> dict:
    overrides = overrides or {}
    teams_all = [t for ts in roster.values() for t in ts]
    stats = {t: empty_stats() for t in teams_all}
    table = {t: {"pts": 0, "gd": 0, "gf": 0} for t in teams_all}  # group standings

    for mt in matches:
        if not mt["completed"]:
            continue
        a, b = mt["team_a"], mt["team_b"]
        if a not in stats or b not in stats:
            continue
        ga, gb = mt["ga"], mt["gb"]
        stats[a]["gf"] += ga; stats[a]["ga"] += gb
        stats[b]["gf"] += gb; stats[b]["ga"] += ga
        for team in (a, b):
            stats[team]["yellow"] += mt["cards"].get(team, {}).get("yellow", 0)
            stats[team]["red"] += mt["cards"].get(team, {}).get("red", 0)

        win = _winner_of(mt)
        if mt["penalties"] or ga == gb:
            stats[a]["draw"] += 1; stats[b]["draw"] += 1
        else:
            loser = b if win == a else a
            stats[win]["win"] += 1; stats[loser]["loss"] += 1

        # milestones from knockout stage appearance
        ms = _STAGE_MILESTONE.get(mt["stage"])
        if ms:
            stats[a][ms] = 1; stats[b][ms] = 1
        if mt["stage"] == "final":
            champ = mt["shootout_winner"] or win
            if champ:
                stats[champ]["winner"] = 1

        # group standings (group stage only)
        if mt["stage"] == "group":
            table[a]["gf"] += ga; table[a]["gd"] += ga - gb
            table[b]["gf"] += gb; table[b]["gd"] += gb - ga
            if ga == gb:
                table[a]["pts"] += 1; table[b]["pts"] += 1
            else:
                table[win]["pts"] += 3

    warnings = []
    forced = overrides.get("force_group_winner", {})
    for g, ts in roster.items():
        if g in forced:
            for t in ts:
                stats[t]["group_winner"] = 1 if t == forced[g] else 0
            continue
        ranked = sorted(ts, key=lambda t: (table[t]["pts"], table[t]["gd"], table[t]["gf"]),
                        reverse=True)
        top, second = ranked[0], ranked[1]
        tie = (table[top]["pts"], table[top]["gd"], table[top]["gf"]) == \
              (table[second]["pts"], table[second]["gd"], table[second]["gf"])
        # only award once the group has actually played; tie -> warn, no award
        played = any(table[t]["pts"] or stats[t]["gf"] or stats[t]["ga"] for t in ts)
        if played and not tie:
            stats[top]["group_winner"] = 1
        elif played and tie:
            warnings.append(f"group {g}: tie for winner between {top} and {second}")

    for team, patch in overrides.get("patch", {}).items():
        if team in stats:
            stats[team].update(patch)

    stats["_warnings"] = warnings
    return stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_team_stats -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/scoring.py tests/test_team_stats.py
git commit -m "feat: derive per-team stats and milestones from matches"
```

---

### Task 11: Scoring — team points (golden formula test)

**Files:**
- Modify: `wc_scorer/scoring.py` (add `WEIGHTS`, `team_points`)
- Create: `tests/test_team_points.py`

**Interfaces:**
- Produces:
  - `WEIGHTS: dict[str, int]` — stat key → point weight.
  - `team_points(stats: dict) -> int`.

- [ ] **Step 1: Write the failing test (golden: compare to the literal workbook formula)**

```python
# tests/test_team_points.py
import re
import unittest
from wc_scorer.xlsx_reader import read_sheet
from wc_scorer.scoring import WEIGHTS, team_points, empty_stats

# Column letters in Results!O formula -> our stat keys.
COL_TO_STAT = {"B": "win", "C": "draw", "D": "loss", "E": "gf", "F": "ga",
               "G": "yellow", "H": "red", "I": "group_winner", "J": "qualify",
               "K": "qf", "L": "sf", "M": "final", "N": "winner"}

class TestGoldenPoints(unittest.TestCase):
    def test_weights_match_workbook_formula(self):
        formula = read_sheet("World Cup Tipping 2026.xlsx", "Results")["O3"]["formula"]
        # e.g. (B3*5)+(C3*3)+...+(F3*-1)+...
        found = {}
        for col, coef in re.findall(r"\(([A-Z])3\*(-?\d+)\)", formula):
            found[COL_TO_STAT[col]] = int(coef)
        self.assertEqual(found, WEIGHTS)

    def test_team_points_one_hot(self):
        for key, weight in WEIGHTS.items():
            s = empty_stats(); s[key] = 1
            self.assertEqual(team_points(s), weight, key)

    def test_team_points_realistic(self):
        s = empty_stats()
        s.update(win=2, draw=1, gf=5, ga=2, yellow=3, red=1, group_winner=1, qualify=1)
        # 2*5 + 1*3 + 5*2 + 2*-1 + 3*-1 + 1*-5 + 1*5 + 1*2 = 10+3+10-2-3-5+5+2 = 20
        self.assertEqual(team_points(s), 20)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_team_points -v`
Expected: FAIL with `cannot import name 'WEIGHTS'`.

- [ ] **Step 3: Write the implementation (append to `wc_scorer/scoring.py`)**

```python
# append to wc_scorer/scoring.py
WEIGHTS = {
    "win": 5, "draw": 3, "loss": 0, "gf": 2, "ga": -1, "yellow": -1, "red": -5,
    "group_winner": 5, "qualify": 2, "qf": 10, "sf": 15, "final": 20, "winner": 30,
}


def team_points(stats: dict) -> int:
    return sum(WEIGHTS[k] * stats.get(k, 0) for k in WEIGHTS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_team_points -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/scoring.py tests/test_team_points.py
git commit -m "feat: team points scoring verified against workbook formula"
```

---

### Task 12: Scoring — per-entrant score with per-country breakdown

**Files:**
- Modify: `wc_scorer/scoring.py` (add `score_entrant`, `score_all`)
- Create: `tests/test_score_entrant.py`

**Interfaces:**
- Produces:
  - `score_entrant(entrant: dict, stats_map: dict) -> dict` → `{"name", "star", "total", "by_country": {team: {"multiplier": int, "components": {stat: pts}, "points": int}}}`. Only teams with multiplier > 0 appear.
  - `score_all(entrants: list, stats_map: dict) -> list` (list of the above).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_score_entrant.py
import unittest
from wc_scorer.scoring import score_entrant, empty_stats

class TestScoreEntrant(unittest.TestCase):
    def test_breakdown_and_total(self):
        mex = empty_stats(); mex.update(win=1, gf=2)          # points = 5 + 4 = 9
        bra = empty_stats(); bra.update(draw=1)               # points = 3
        stats = {"Mexico": mex, "Brazil": bra, "Haiti": empty_stats()}
        entrant = {"name": "Tester", "starred_team": "Mexico",
                   "multipliers": {"Mexico": 5, "Brazil": 3, "Haiti": 0}}
        r = score_entrant(entrant, stats)
        self.assertEqual(r["by_country"]["Mexico"]["points"], 45)   # 5 * 9
        self.assertEqual(r["by_country"]["Mexico"]["components"]["win"], 25)  # 5*5*1
        self.assertEqual(r["by_country"]["Mexico"]["components"]["gf"], 20)   # 5*2*2
        self.assertEqual(r["by_country"]["Brazil"]["points"], 9)    # 3 * 3
        self.assertNotIn("Haiti", r["by_country"])                  # mult 0 excluded
        self.assertEqual(r["total"], 54)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_score_entrant -v`
Expected: FAIL with `cannot import name 'score_entrant'`.

- [ ] **Step 3: Write the implementation (append to `wc_scorer/scoring.py`)**

```python
# append to wc_scorer/scoring.py
def score_entrant(entrant: dict, stats_map: dict) -> dict:
    by_country = {}
    total = 0
    for team, mult in entrant["multipliers"].items():
        if mult <= 0:
            continue
        stats = stats_map.get(team) or empty_stats()
        components = {k: mult * WEIGHTS[k] * stats.get(k, 0)
                      for k in WEIGHTS if stats.get(k, 0)}
        points = mult * team_points(stats)
        by_country[team] = {"multiplier": mult, "components": components, "points": points}
        total += points
    return {"name": entrant["name"], "star": entrant["starred_team"],
            "total": total, "by_country": by_country}


def score_all(entrants: list, stats_map: dict) -> list:
    return [score_entrant(e, stats_map) for e in entrants]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_score_entrant -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/scoring.py tests/test_score_entrant.py
git commit -m "feat: per-entrant scoring with per-country breakdown"
```

---

### Task 13: Reporting — ladder + breakdown (console / CSV / Markdown)

**Files:**
- Create: `wc_scorer/report.py`
- Create: `tests/test_report.py`

**Interfaces:**
- Consumes: `score_all` results, `teams.team_group`.
- Produces:
  - `ladder(results: list) -> list` (results sorted by total desc, then name).
  - `render_ladder(results: list) -> str`
  - `render_breakdown(result: dict, team_group: dict) -> str`
  - `write_csv(results: list, team_group: dict, out_dir: str) -> None` (writes `ladder.csv`, `breakdown.csv`)
  - `write_markdown(results: list, team_group: dict, out_path: str) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
import unittest, os, tempfile
from wc_scorer import report

RESULTS = [
    {"name": "Beth", "star": "Brazil", "total": 50,
     "by_country": {"Brazil": {"multiplier": 5, "components": {"win": 25}, "points": 25}}},
    {"name": "Al", "star": "Spain", "total": 90,
     "by_country": {"Spain": {"multiplier": 5, "components": {"win": 25}, "points": 25}}},
]
TEAM_GROUP = {"Brazil": "C", "Spain": "H"}

class TestReport(unittest.TestCase):
    def test_ladder_sorted_desc(self):
        rows = report.ladder(RESULTS)
        self.assertEqual([r["name"] for r in rows], ["Al", "Beth"])

    def test_render_ladder_contains_rank(self):
        text = report.render_ladder(RESULTS)
        self.assertIn("Al", text)
        self.assertIn("90", text)

    def test_write_csv_and_md(self):
        with tempfile.TemporaryDirectory() as d:
            report.write_csv(RESULTS, TEAM_GROUP, d)
            report.write_markdown(RESULTS, TEAM_GROUP, os.path.join(d, "report.md"))
            self.assertTrue(os.path.exists(os.path.join(d, "ladder.csv")))
            self.assertTrue(os.path.exists(os.path.join(d, "breakdown.csv")))
            self.assertTrue(os.path.exists(os.path.join(d, "report.md")))
            with open(os.path.join(d, "breakdown.csv")) as f:
                self.assertIn("multiplier", f.readline())

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_report -v`
Expected: FAIL with `No module named 'wc_scorer.report'`.

- [ ] **Step 3: Write the implementation**

```python
# wc_scorer/report.py
import csv
import os

_BREAKDOWN_COLS = ["win", "draw", "loss", "gf", "ga", "yellow", "red",
                   "group_winner", "qualify", "qf", "sf", "final", "winner"]


def ladder(results: list) -> list:
    return sorted(results, key=lambda r: (-r["total"], r["name"]))


def render_ladder(results: list) -> str:
    lines = ["Rank  Total  Star            Name",
             "----  -----  --------------  --------------------"]
    for i, r in enumerate(ladder(results), 1):
        lines.append(f"{i:>4}  {r['total']:>5}  {r['star'][:14]:<14}  {r['name']}")
    return "\n".join(lines)


def render_breakdown(result: dict, team_group: dict) -> str:
    lines = [f"\n{result['name']}  —  total {result['total']}  (★ {result['star']})",
             f"  {'Country':<16}{'Grp':<4}{'x':<3}{'Pts':>5}   detail"]
    rows = sorted(result["by_country"].items(), key=lambda kv: -kv[1]["points"])
    for team, info in rows:
        detail = ", ".join(f"{k}:{v}" for k, v in info["components"].items())
        grp = team_group.get(team, "?")
        lines.append(f"  {team:<16}{grp:<4}{info['multiplier']:<3}{info['points']:>5}   {detail}")
    return "\n".join(lines)


def write_csv(results: list, team_group: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "ladder.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "name", "star", "total"])
        for i, r in enumerate(ladder(results), 1):
            w.writerow([i, r["name"], r["star"], r["total"]])
    with open(os.path.join(out_dir, "breakdown.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entrant", "country", "group", "multiplier"] + _BREAKDOWN_COLS + ["points"])
        for r in ladder(results):
            for team, info in sorted(r["by_country"].items(), key=lambda kv: -kv[1]["points"]):
                comps = info["components"]
                w.writerow([r["name"], team, team_group.get(team, "?"), info["multiplier"]]
                           + [comps.get(c, 0) for c in _BREAKDOWN_COLS] + [info["points"]])


def write_markdown(results: list, team_group: dict, out_path: str) -> None:
    parts = ["# World Cup Tipping — Standings\n", "## Ladder\n",
             "| Rank | Name | ★ | Total |", "|---:|---|---|---:|"]
    for i, r in enumerate(ladder(results), 1):
        parts.append(f"| {i} | {r['name']} | {r['star']} | {r['total']} |")
    parts.append("\n## Breakdowns\n")
    for r in ladder(results):
        parts.append(f"### {r['name']} — {r['total']} (★ {r['star']})\n")
        parts.append("| Country | Grp | × | Points |")
        parts.append("|---|---|---:|---:|")
        for team, info in sorted(r["by_country"].items(), key=lambda kv: -kv[1]["points"]):
            parts.append(f"| {team} | {team_group.get(team, '?')} | {info['multiplier']} | {info['points']} |")
        parts.append("")
    with open(out_path, "w") as f:
        f.write("\n".join(parts))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_report -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/report.py tests/test_report.py
git commit -m "feat: ladder + per-country breakdown rendering and CSV/MD export"
```

---

### Task 14: CLI wiring + end-to-end smoke

**Files:**
- Create: `wc_scorer/cli.py`
- Create: `wc_scorer/__main__.py`
- Create: `tests/test_e2e.py`

**Interfaces:**
- Consumes: every module above.
- Produces:
  - `cli.run_extract(args) -> int`, `cli.run_score(args) -> int`, `cli.main(argv=None) -> int`.
  - `cli.compute(ref_dir, dates, refresh, cache_dir, overrides_path) -> list` (the scored results, used by tests).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_e2e.py
import unittest
from wc_scorer import cli

class TestEndToEnd(unittest.TestCase):
    def test_compute_against_real_data(self):
        results = cli.compute(ref_dir="data/reference", dates=None,
                              refresh=False, cache_dir="data/cache",
                              overrides_path=None)
        self.assertEqual(len(results), 63)
        for r in results:
            self.assertIsInstance(r["total"], int)
        # Highest scorer should be positive once group games are in.
        self.assertGreater(max(r["total"] for r in results), 0)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_e2e -v`
Expected: FAIL with `No module named 'wc_scorer.cli'`.

- [ ] **Step 3: Write the implementation**

```python
# wc_scorer/cli.py
import argparse
import json
import os

from . import espn, extract, rankings, report, scoring, teams


def compute(ref_dir, dates, refresh, cache_dir, overrides_path):
    roster = teams.load_roster(ref_dir)
    name_map = teams.load_name_map(ref_dir)
    entrants = rankings.load_entrants(ref_dir)
    raw = espn.fetch(dates or espn.DEFAULT_DATES, cache_dir=cache_dir, refresh=refresh)
    matches = espn.parse(raw, name_map)
    overrides = None
    if overrides_path and os.path.exists(overrides_path):
        with open(overrides_path) as f:
            overrides = json.load(f)
    stats = scoring.team_stats(matches, roster, overrides=overrides)
    warnings = stats.pop("_warnings", [])
    for w in warnings:
        print(f"WARNING: {w}")
    return scoring.score_all(entrants, stats)


def run_extract(args) -> int:
    names = espn.team_names(espn.fetch(args.dates or espn.DEFAULT_DATES,
                                       cache_dir=args.cache))
    summary = extract.extract(args.rankings, out_dir=args.out, espn_names=names,
                              now=args.now)
    print(f"Extracted: {summary['entrants']} entrants, {summary['roster']} teams, "
          f"{summary['name_map']} name mappings.")
    if summary["exceptions"]:
        print(f"UNMAPPED ESPN NAMES (add to MANUAL_ALIASES): {summary['exceptions']}")
        return 1
    return 0


def run_score(args) -> int:
    results = compute(args.ref, args.dates, args.refresh, args.cache, args.overrides)
    tg = teams.team_group(teams.load_roster(args.ref))
    fmts = args.format.split(",")
    if "console" in fmts:
        print(report.render_ladder(results))
        for r in report.ladder(results):
            print(report.render_breakdown(r, tg))
    if "csv" in fmts:
        report.write_csv(results, tg, args.out)
    if "md" in fmts:
        report.write_markdown(results, tg, os.path.join(args.out, "report.md"))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="wc_scorer")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("extract", help="parse the workbook into reference JSON")
    pe.add_argument("--rankings", default="World Cup Tipping 2026.xlsx")
    pe.add_argument("--out", default="data/reference")
    pe.add_argument("--cache", default="data/cache")
    pe.add_argument("--dates", default=None)
    pe.add_argument("--now", default="")
    pe.set_defaults(func=run_extract)

    ps = sub.add_parser("score", help="score the competition from the live feed")
    ps.add_argument("--ref", default="data/reference")
    ps.add_argument("--cache", default="data/cache")
    ps.add_argument("--dates", default=None)
    ps.add_argument("--refresh", action="store_true")
    ps.add_argument("--overrides", default="data/overrides.json")
    ps.add_argument("--format", default="console,csv,md")
    ps.add_argument("--out", default="out")
    ps.set_defaults(func=run_score)

    args = p.parse_args(argv)
    return args.func(args)
```

```python
# wc_scorer/__main__.py
import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the smoke test and a real scoring run**

Run: `python3 -m unittest tests.test_e2e -v`
Expected: PASS.

Run: `python3 -m wc_scorer score --refresh`
Expected: prints the ladder (63 rows) + per-country breakdowns; writes `out/ladder.csv`, `out/breakdown.csv`, `out/report.md`.

- [ ] **Step 5: Commit**

```bash
git add wc_scorer/cli.py wc_scorer/__main__.py tests/test_e2e.py
git commit -m "feat: CLI with extract/score commands and end-to-end scoring"
```

---

### Task 15: Full test sweep + README

**Files:**
- Create: `README.md`
- Create: `data/overrides.json` (empty template)

**Interfaces:**
- None (documentation + convenience).

- [ ] **Step 1: Run the entire test suite**

Run: `python3 -m unittest discover -s tests -p "test_*.py" -v`
Expected: ALL tests PASS.

- [ ] **Step 2: Write an empty overrides template**

```json
{
  "force_group_winner": {},
  "patch": {}
}
```

- [ ] **Step 3: Write `README.md`**

````markdown
# World Cup 2026 Tipping Scorer

Scores the family World Cup tipping competition from live results.

## Usage

```bash
# One-off (or whenever the workbook changes): build reference data from the .xlsx
python3 -m wc_scorer extract

# Score using the latest results (re-fetches the live feed)
python3 -m wc_scorer score --refresh
```

Outputs the ladder + a per-country breakdown for every entrant to the console,
and writes `out/ladder.csv`, `out/breakdown.csv`, `out/report.md`.

## How scoring works

Two layers, reproducing the original workbook exactly:
1. Each team earns performance points: win 5, draw 3 (incl. penalty games),
   goals-for 2, goals-against −1, yellow −1, red −5, group winner 5, qualify 2,
   QF 10, SF 15, final 20, winner 30.
2. Each entrant multiplies each backed team's points by their rank (★ 5, 1st ×3,
   2nd ×2, 3rd ×1, unranked ×0).

## Data sources

- Rankings/roster: extracted by code from `World Cup Tipping 2026.xlsx` into
  `data/reference/*.json` (never hand-typed).
- Live results: ESPN unofficial scoreboard API, cached under `data/cache/`.

## Manual overrides

Edit `data/overrides.json` to force a group winner (tiebreaker edge cases) or
patch a team's stats if the feed is wrong. Group-winner ties print a WARNING.

## Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
````

- [ ] **Step 4: Commit**

```bash
git add README.md data/overrides.json
git commit -m "docs: add README and overrides template"
```

---

## Self-Review

**Spec coverage:**
- Data source (ESPN, cached) → Task 5; parse → Task 9. ✅
- Extract-don't-transcribe / reference JSON → Tasks 3,4,6,7. ✅
- Scoring layer 1 (team points, golden test) → Tasks 10,11. ✅
- Scoring layer 2 (per-country breakdown) → Task 12. ✅
- Roster/name-map/entrants loaders → Task 8. ✅
- Ladder + breakdown + CSV/MD → Task 13. ✅
- CLI extract/score → Task 14. ✅
- Name map (6 verified aliases, placeholder filter, hard error on unknown) → Tasks 6,8,9. ✅
- Penalty KO = draw both; milestones from stage; group-winner ties flagged; overrides → Task 10. ✅
- 63 entrants / 48 teams invariants, self-closing-cell handling → Tasks 2,4,7. ✅
- Star from grid not Ladder label → Task 4. ✅
- Testing: golden formula, name-map, derivation incl. penalty/second-yellow, e2e smoke → Tasks 9,10,11,14. ✅

**Open items (from spec, intentionally deferred):** penalty/shootout and knockout-stage slugs cannot be validated until knockouts begin; `stage_of`/penalty handling is written to documented fields and is covered by the overrides hook. Re-validate when the Round of 32 starts.

**Placeholder scan:** none — every step contains runnable code/commands.

**Type consistency:** match dict keys (`team_a/team_b/ga/gb/stage/completed/penalties/shootout_winner/cards`), stats keys (`_STAT_KEYS`), and result keys (`name/star/total/by_country`) are used consistently across Tasks 9–14.
