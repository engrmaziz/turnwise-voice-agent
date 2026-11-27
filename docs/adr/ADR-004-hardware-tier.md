# ADR-004: Hardware tier

- Status: Proposed
- Date: 2026-11-26

## Context

ADR-003 keeps the model stack Proposed until a bench on this machine records ASR finalize, language-model time-to-first-token, and TTS first-chunk. The tiers in `docs/plan/00_front_matter.md` are CPU-only, 8 GB VRAM, and 16 GB+ VRAM. Naming one of those from a missing row would freeze a guess.

Host: `Windows-10-10.0.26300-SP0`
Python: `3.11.9`
JSON: `docs/results/bench/20261126T200406Z.json`

## Decision

The operator machine is **16 GB+**. nvidia-smi VRAM 24 GB. ADR-003 was later Accepted with named Zipformer / Piper / Ollama builds; this hardware-tier ADR stays Proposed.

## Consequences

- A second host writes a second JSON file. It does not edit this one.
- Model names in settings stay unset until ADR-003 is Accepted.
- `docs/benchmarks.md` is generated from the same JSON as this ADR.
