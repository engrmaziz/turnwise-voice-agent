"""Shared model worker pools.

``VadPool`` and the ASR stub pool are process-wide. Real ASR, TTS, and the LLM
client still wait on measured rows in ADR-003 and ADR-006.
"""
