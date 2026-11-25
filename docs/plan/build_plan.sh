#!/usr/bin/env bash
# Concatenate the twelve plan files and build Markdown plus DOCX.
# Word does not render Mermaid. This script extracts every fenced mermaid
# block, renders PNG with mermaid-cli (mmdc), and rewrites the fence to an
# image before pandoc runs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PLAN="${ROOT}/docs/plan"
OUT_DIR="${ROOT}/docs/plan/_build"
IMG_DIR="${OUT_DIR}/mermaid"
CONCAT="${OUT_DIR}/Turnwise_Execution_Plan.md"
DOCX="${ROOT}/Turnwise_Execution_Plan.docx"
REF="${ROOT}/reference.docx"

mkdir -p "${IMG_DIR}"

FILES=(
  "${PLAN}/00_front_matter.md"
  "${PLAN}/01_phase_foundation.md"
  "${PLAN}/02_phase_audio_front_end.md"
  "${PLAN}/03_phase_asr_spoken_form.md"
  "${PLAN}/04_phase_turn_taking.md"
  "${PLAN}/05_phase_spoken_nlu.md"
  "${PLAN}/06_phase_dialogue_tools.md"
  "${PLAN}/07_phase_tts.md"
  "${PLAN}/08_phase_paralinguistics_safety.md"
  "${PLAN}/09_phase_evaluation.md"
  "${PLAN}/10_phase_hardening_launch.md"
  "${PLAN}/11_appendices.md"
)

for f in "${FILES[@]}"; do
  if [[ ! -f "${f}" ]]; then
    echo "missing ${f}" >&2
    exit 1
  fi
done

python3 - "${CONCAT}" "${IMG_DIR}" "${FILES[@]}" <<'PY'
import pathlib
import re
import subprocess
import sys

concat_path = pathlib.Path(sys.argv[1])
img_dir = pathlib.Path(sys.argv[2])
sources = [pathlib.Path(p) for p in sys.argv[3:]]
img_dir.mkdir(parents=True, exist_ok=True)
concat_path.parent.mkdir(parents=True, exist_ok=True)

fence = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
parts: list[str] = []
n = 0
for src in sources:
    text = src.read_text(encoding="utf-8")
    def repl(match: re.Match[str]) -> str:
        global n
        n += 1
        mmd = img_dir / f"diagram_{n:02d}.mmd"
        png = img_dir / f"diagram_{n:02d}.png"
        mmd.write_text(match.group(1).strip() + "\n", encoding="utf-8")
        cmd = ["mmdc", "-i", str(mmd), "-o", str(png), "-b", "white"]
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError as exc:
            raise SystemExit(
                "mmdc not found. Install @mermaid-js/mermaid-cli and retry."
            ) from exc
        rel = pathlib.Path("mermaid") / png.name
        return f"![Mermaid diagram {n}]({rel.as_posix()})\n"
    parts.append(fence.sub(repl, text).rstrip() + "\n\n")

concat_path.write_text("".join(parts), encoding="utf-8")
print(f"wrote {concat_path} with {n} mermaid images")
PY

cp "${CONCAT}" "${ROOT}/Turnwise_Execution_Plan.md"

PANDOC=(pandoc "${CONCAT}" -o "${DOCX}" --toc --toc-depth=3 --number-sections --resource-path="${OUT_DIR}")
if [[ -f "${REF}" ]]; then
  PANDOC+=(--reference-doc="${REF}")
fi
"${PANDOC[@]}"
echo "wrote ${DOCX}"
