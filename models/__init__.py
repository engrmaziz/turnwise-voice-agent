"""Shared model worker pools.

``VadPool``, the ASR stub pool, the turn-completeness scorer, the NLU
student, and the TTS pool are process-wide. Empty ``tts_backend`` is the
silence stub. ``piper`` loads ``en_US-amy-low`` when the ONNX is on disk.
Real ASR and the LLM client still wait on measured rows in ADR-003 and
ADR-006.
"""
