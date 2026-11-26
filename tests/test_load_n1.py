"""One concurrent scripted session writes JSON that does not pretend to be 900."""

from pathlib import Path

from evals.harness import default_eval_settings
from evals.load import run_one_n


async def test_load_n1_reports_actual_n_and_stub_play_ack(tmp_path: Path) -> None:
    out = tmp_path / "load_n1.json"
    payload = await run_one_n(
        n=1,
        scenario_id="book_avery",
        scenario_dir=Path("evals/scenarios"),
        settings=default_eval_settings(),
        out=out,
    )
    assert payload["n"] == 1
    samples = payload["ttfa_samples"]
    assert isinstance(samples, int)
    assert samples >= 1
    assert payload["ttfa_p95_s"] is not None
    assert payload["ttfa_path"] == "stub_play_ack"
    assert payload["product_quote"] is False
    assert payload["adr004_tier"] == "blocked"
    assert payload["status"] in {"hit", "miss"}
    assert "platform" in payload
    assert out.is_file()
