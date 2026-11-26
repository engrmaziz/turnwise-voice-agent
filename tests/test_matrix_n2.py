"""Matrix JSON reports actual n. A 2-call run does not pretend it was 900."""

from pathlib import Path

from evals.harness import default_eval_settings
from evals.run_matrix import run_matrix


async def test_matrix_n2_reports_actual_n(tmp_path: Path) -> None:
    out = tmp_path / "matrix.json"
    payload = await run_matrix(
        n=2,
        scenario_dir=Path("evals/scenarios"),
        smoke_path=Path("evals/scenarios/smoke.yaml"),
        out=out,
        settings=default_eval_settings(),
    )
    assert payload["n"] == 2
    assert payload["requested_n"] == 2
    assert "elapsed_s" in payload
    assert payload["time_scale"] == 0.0
    assert out.is_file()
