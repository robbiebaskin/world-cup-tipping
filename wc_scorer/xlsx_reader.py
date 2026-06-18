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
