"""A millisecond or percent in the README SLO table must cite docs/results/."""

import re
from pathlib import Path

_NUMBER = re.compile(
    r"(?<![A-Za-z_])(?:\d+(?:\.\d+)?)\s*(?:ms|%|seconds?)?",
    re.IGNORECASE,
)


def test_slo_table_rows_cite_results() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    start = text.index("## SLO")
    rest = text[start:]
    end = rest.index("\n## ", 1)
    section = rest[:end]
    rows = [
        line
        for line in section.splitlines()
        if line.startswith("|") and "---" not in line and "Metric" not in line
    ]
    assert rows, "SLO table missing"
    for row in rows:
        if not _NUMBER.search(row):
            continue
        assert "docs/results/" in row, row


def test_load_cell_cites_phase10_load() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "docs/results/phase10_load.md" in text
