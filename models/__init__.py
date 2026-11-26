"""Shared model worker pools.

``VadPool``, the ASR stub pool, the turn-completeness scorer, and the NLU
student are process-wide. Real ASR, TTS, and the LLM client still wait on
measured rows in ADR-003 and ADR-006.
"""
