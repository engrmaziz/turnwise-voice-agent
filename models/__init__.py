"""Shared model worker pools.

``VadPool``, the ASR stub pool, and the turn-completeness scorer are
process-wide. Real ASR, TTS, and the LLM client still wait on measured rows
in ADR-003 and ADR-006.
"""
