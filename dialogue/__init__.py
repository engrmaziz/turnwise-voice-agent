"""Dialogue FSM, slot schemas, and validators.

``regex_slots`` is an ablation matcher and is not imported by ``server.app``.
The FSM remains the only writer of dialogue state. See docs/adr/ADR-001-fsm-first.md.
"""
