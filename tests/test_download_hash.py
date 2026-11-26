"""A mismatched sha256 fails the download lock."""

from pathlib import Path

import pytest

from scripts.download_models import LockError, verify_file


def test_fake_file_hash_mismatch(tmp_path: Path) -> None:
    blob = tmp_path / "model.bin"
    blob.write_bytes(b"not-a-weight")
    with pytest.raises(LockError, match="hash mismatch"):
        verify_file(blob, "0" * 64)
