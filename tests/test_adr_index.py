"""Appendix I lists every ADR file on disk."""

import re
from pathlib import Path

_ADR = re.compile(r"ADR-(\d+)")
_INDEX_ROW = re.compile(r"^\| (\d{3}) \|", re.MULTILINE)


def test_appendix_i_lists_every_adr_file() -> None:
    files = sorted(Path("docs/adr").glob("ADR-*.md"))
    assert files
    numbers = []
    for path in files:
        match = _ADR.search(path.name)
        assert match, path
        numbers.append(match.group(1).zfill(3))
    appendix = Path("docs/plan/11_appendices.md").read_text(encoding="utf-8")
    start = appendix.index("## I. ADR index")
    section = appendix[start : appendix.index("## J.")]
    listed = set(_INDEX_ROW.findall(section))
    missing = [number for number in numbers if number not in listed]
    assert missing == []
