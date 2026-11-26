"""Record CREMA-D / RAVDESS licenses. Wavs stay gitignored. No CI download."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CREMA_LICENSE = "https://github.com/CheyneyComputerScience/CREMA-D/blob/master/LICENSE.txt"
CREMA_ODBL = "http://opendatacommons.org/licenses/odbl/1.0/"
CREMA_DBCL = "http://opendatacommons.org/licenses/dbcl/1.0/"
RAVDESS_RECORD = "https://zenodo.org/records/1188976"
RAVDESS_CC = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

CREMA_NOTICE = f"""CREMA-D
License file: {CREMA_LICENSE}
ODbL 1.0: {CREMA_ODBL}
DbCL 1.0: {CREMA_DBCL}
Fetch wavs into this directory. Do not commit them.
"""

RAVDESS_NOTICE = f"""RAVDESS
Zenodo: {RAVDESS_RECORD}
CC BY-NC-SA 4.0: {RAVDESS_CC}
Non-commercial. Product use needs a paid license.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("crema", "ravdess", "all"), default="all")
    parser.add_argument("--dest", type=Path, default=Path("training/emotion/raw"))
    parser.add_argument(
        "--research-nc",
        action="store_true",
        help="Acknowledge RAVDESS is research-only under CC BY-NC-SA 4.0",
    )
    args = parser.parse_args(argv)
    if args.dataset in {"ravdess", "all"} and not args.research_nc:
        sys.stderr.write(
            "RAVDESS is CC BY-NC-SA 4.0 (non-commercial). "
            "Pass --research-nc for research-only use, or --dataset crema.\n"
            f"License: {RAVDESS_CC}\n"
        )
        return 2
    dest: Path = args.dest
    dest.mkdir(parents=True, exist_ok=True)
    if args.dataset in {"crema", "all"}:
        (dest / "CREMA-D.LICENSE.txt").write_text(CREMA_NOTICE, encoding="utf-8")
        sys.stdout.write(f"crema license recorded under {dest} ({CREMA_ODBL})\n")
    if args.dataset in {"ravdess", "all"}:
        (dest / "RAVDESS.LICENSE.txt").write_text(RAVDESS_NOTICE, encoding="utf-8")
        sys.stdout.write(f"ravdess license recorded under {dest} ({RAVDESS_CC})\n")
    sys.stdout.write("wav fetch is manual; this script does not pull corpora\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
