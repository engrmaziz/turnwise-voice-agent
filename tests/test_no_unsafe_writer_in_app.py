"""The unsafe loop writer is not a product import."""

from pathlib import Path


def test_server_does_not_import_unsafe_writer() -> None:
    root = Path("server")
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "unsafe_llm_writer" in text or "evals.unsafe" in text:
            hits.append(str(path))
    assert hits == []


def test_eval_text_inject_is_absent_from_websocket() -> None:
    source = Path("server/ws.py").read_text(encoding="utf-8")
    assert "eval_text_inject" not in source
    assert "text_inject" not in source
