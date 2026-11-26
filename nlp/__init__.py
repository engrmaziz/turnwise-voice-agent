"""Spoken-form NLP: ITN, temporal grounding, hotwords, LocalAgreement-2.

Date resolution is deterministic. The LLM does not do date arithmetic.
Backchannel filtering is state-dependent and lives in ``nlp.backchannel``.
Phonetic resolve and self-repair live in ``nlp.phonetic`` and ``nlp.disfluency``.
"""
