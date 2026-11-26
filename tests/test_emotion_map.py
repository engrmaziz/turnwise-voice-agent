"""CREMA-D and RAVDESS labels map onto three classes. Unmapped labels drop."""

from pathlib import Path

from scripts.download_emotion import main as download_main

from training.emotion.map_labels import (
    map_crema,
    map_file,
    map_ravdess,
    map_tree,
)


def test_crema_happy_neutral_angry_fear() -> None:
    assert map_crema("HAP") == "calm"
    assert map_crema("NEU") == "calm"
    assert map_crema("ANG") == "frustrated"
    assert map_crema("DIS") == "frustrated"
    assert map_crema("FEA") == "distressed"
    assert map_crema("SAD") == "distressed"


def test_ravdess_table_and_surprise_unmapped() -> None:
    assert map_ravdess("01") == "calm"
    assert map_ravdess("03") == "calm"
    assert map_ravdess("05") == "frustrated"
    assert map_ravdess("06") == "distressed"
    assert map_ravdess("08") is None


def test_filename_parsers_and_dropped_count(tmp_path: Path) -> None:
    crema = tmp_path / "crema" / "1001_DFA_ANG_XX.wav"
    surprise = tmp_path / "ravdess" / "03-01-08-01-02-01-12.wav"
    crema.parent.mkdir()
    surprise.parent.mkdir()
    crema.write_bytes(b"")
    surprise.write_bytes(b"")
    angry = map_file(crema, "crema")
    assert angry.mapped == "frustrated"
    dropped = map_file(surprise, "ravdess")
    assert dropped.mapped is None
    rows, count = map_tree(surprise.parent, "ravdess")
    assert count == 1
    assert len(rows) == 1


def test_download_ravdess_exits_2_without_research_flag() -> None:
    assert download_main(["--dataset", "ravdess"]) == 2


def test_download_crema_records_license(tmp_path: Path) -> None:
    dest = tmp_path / "raw"
    assert download_main(["--dataset", "crema", "--dest", str(dest)]) == 0
    notice = (dest / "CREMA-D.LICENSE.txt").read_text(encoding="utf-8")
    assert "opendatacommons.org/licenses/odbl/1.0/" in notice
