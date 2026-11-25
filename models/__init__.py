"""Shared model worker pools.

``models.vad_pool.VadPool`` is the first process-wide worker. ASR, TTS, and the
LLM client still wait on measured rows in ADR-003.
"""
