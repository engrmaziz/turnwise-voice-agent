"""Grafana dashboard has a panel id per appendix G row. Queries use _total on counters."""

import json
from pathlib import Path


def test_appendix_g_panel_ids() -> None:
    dashboard = json.loads(
        Path("infra/grafana/dashboards/turnwise.json").read_text(encoding="utf-8")
    )
    panels = {int(panel["id"]): panel for panel in dashboard["panels"]}
    required = {
        1: "turnwise_stage_latency_seconds",
        2: "turnwise_queue_depth",
        3: "turnwise_events_dropped_stale_total",
        4: "turnwise_stage_errors_total",
        5: "turnwise_barge_in_total",
        6: "turnwise_ttfa_seconds",
        7: "turnwise_ttfa_content_seconds",
        8: "turnwise_task_outcome_total",
        9: "turnwise_false_barge_in_total",
        10: "turnwise_early_cutoff_total",
        11: "turnwise_tts_cache_hits_total",
        12: "turnwise_degraded_total",
    }
    for panel_id, needle in required.items():
        panel = panels[panel_id]
        exprs = " ".join(str(target.get("expr", "")) for target in panel["targets"])
        assert needle in exprs, panel_id
        if needle.endswith("_total"):
            assert "_total" in exprs
