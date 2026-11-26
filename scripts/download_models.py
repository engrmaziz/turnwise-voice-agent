"""Download locked model files and refuse a sha256 mismatch."""

from __future__ import annotations

import argparse
import hashlib
import sys
import tomllib
import urllib.request
from pathlib import Path

LOCK_PATH = Path("models/lock.toml")


class LockError(ValueError):
    """Lock file or hash check failed."""


def load_lock(path: Path) -> dict[str, object]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LockError("lock must be a mapping")
    return raw


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify_file(path: Path, expected: str) -> None:
    digest = sha256_bytes(path.read_bytes())
    if digest != expected:
        raise LockError(f"hash mismatch for {path}: got {digest} expected {expected}")


def download_one(row: dict[str, object], *, required: bool) -> str:
    name = str(row.get("name") or "")
    dest = Path(str(row.get("path") or ""))
    expected = str(row.get("sha256") or "").strip()
    url = str(row.get("url") or "").strip()
    if not name or not dest:
        raise LockError("model row needs name and path")
    if not expected:
        if required:
            raise LockError(f"{name} has empty sha256 and --required is set")
        return f"skipped:{name}:empty_sha256"
    if dest.is_file():
        verify_file(dest, expected)
        return f"ok:{name}:existing"
    if not url:
        raise LockError(f"{name} missing url")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read()
    digest = sha256_bytes(payload)
    if digest != expected:
        raise LockError(f"hash mismatch for {name}: got {digest} expected {expected}")
    dest.write_bytes(payload)
    return f"ok:{name}:downloaded"


def run(lock_path: Path, *, required: bool) -> list[str]:
    payload = load_lock(lock_path)
    lock_required = bool(payload.get("required", False))
    require = required or lock_required
    models = payload.get("model")
    if not isinstance(models, list):
        raise LockError("lock needs [[model]] rows")
    results: list[str] = []
    for row in models:
        if not isinstance(row, dict):
            raise LockError("model row must be a mapping")
        results.append(download_one(row, required=require))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK_PATH)
    parser.add_argument("--required", action="store_true")
    args = parser.parse_args(argv)
    try:
        rows = run(args.lock, required=args.required)
    except LockError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    for row in rows:
        sys.stdout.write(row + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
