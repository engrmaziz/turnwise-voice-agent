"""One concurrent scripted session writes JSON that does not pretend to be 900."""

from pathlib import Path

from evals.harness import default_eval_settings
from evals.load import run_one_n


async def test_load_n1_reports_actual_n(tmp_path: Path) -> None:
    out = tmp_path / "load_n1.json"
    payload = await run_one_n(
        n=1,
        scenario_id="book_avery",
        scenario_dir=Path("evals/scenarios"),
        settings=default_eval_settings(),
        out=out,
    )
    assert payload["n"] == 1
    assert payload["ttfa_samples"] == 0
    assert payload["ttfa_p95_s"] is None
    assert payload["status"] == "miss"
    assert payload["adr004_tier"] == "blocked"
    assert "platform" in payload
    assert out.is_file()
