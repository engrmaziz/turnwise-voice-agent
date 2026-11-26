"""Render Mermaid from the transition table. The table is the source of truth."""

from __future__ import annotations

from dialogue.table import Table, load_table

# Display order matches appendix C so whitespace-normalized equality can hold.
_EDGE_ORDER = (
    ("GREET", "IDENTIFY_PATIENT"),
    ("IDENTIFY_PATIENT", "COLLECT_INTENT"),
    ("IDENTIFY_PATIENT", "HANDOFF"),
    ("COLLECT_INTENT", "COLLECT_SLOTS"),
    ("COLLECT_INTENT", "FAQ"),
    ("FAQ", "COLLECT_INTENT"),
    ("COLLECT_SLOTS", "CONFIRM"),
    ("COLLECT_SLOTS", "COLLECT_SLOTS"),
    ("CONFIRM", "EXECUTE"),
    ("CONFIRM", "COLLECT_SLOTS"),
    ("EXECUTE", "CLOSE"),
    ("EXECUTE", "COLLECT_SLOTS"),
    ("EXECUTE", "HANDOFF"),
    ("CLOSE", "COLLECT_SLOTS"),
    ("GREET", "URGENT"),
    ("IDENTIFY_PATIENT", "URGENT"),
    ("COLLECT_INTENT", "URGENT"),
    ("COLLECT_SLOTS", "URGENT"),
    ("CONFIRM", "URGENT"),
    ("FAQ", "URGENT"),
    ("CLOSE", "HANDOFF"),
)


def render_mermaid(table: Table | None = None) -> str:
    loaded = table if table is not None else load_table()
    edges = {(row.state, row.next_state) for row in loaded.rows}
    lines = ["stateDiagram-v2", "  [*] --> GREET"]
    for src, dst in _EDGE_ORDER:
        if (src, dst) in edges:
            lines.append(f"  {src} --> {dst}")
    return "\n".join(lines) + "\n"


def normalize(text: str) -> str:
    return "\n".join(line.strip() for line in text.strip().splitlines() if line.strip())
