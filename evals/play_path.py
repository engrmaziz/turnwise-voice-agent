"""Scripted caller plus TTS play-ack. Not a product TTFA quote (ADR-012)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from evals.caller_scripted import scripted_turns
from evals.harness import RunTrace, _roster, _seed_if_book, eval_now
from evals.schema import Scenario
from models.llm_client import LlmClient
from models.tts_cache import TtsCache
from models.tts_pool import TtsPool
from pipeline.event import EventKind
from pipeline.metrics import StageMetrics
from pipeline.session import Session
from pipeline.stages.audio_out import AudioOutHandler
from pipeline.stages.chunker import ChunkerHandler
from pipeline.stages.dialogue import DialogueHandler
from pipeline.stages.tts_norm import TtsNormHandler
from server.config import Settings
from server.playback import PlaybackCursor
from tools.calendar import list_appointments, migrate


async def run_scripted_play(
    scenario: Scenario,
    *,
    db: Path,
    settings: Settings,
    metrics: StageMetrics,
    pool: TtsPool,
    cache: TtsCache | None = None,
    llm: LlmClient | None = None,
) -> RunTrace:
    """Stamp TURN_END, run dialogue→chunker→TN→audio_out, ack play index 0."""
    if not settings.eval_text_inject:
        raise RuntimeError("eval_text_inject must be true in the eval process")
    timezone = ZoneInfo(settings.clinic_timezone)
    now = eval_now(scenario, timezone)
    names = _roster(settings)
    migrate(db, names)
    session = Session(str(uuid4()), now=now, timezone=timezone)
    session.barge_in_enabled = True
    phrases = cache if cache is not None else TtsCache(warmup_ids=frozenset())
    playback = PlaybackCursor()
    audio_out = AudioOutHandler(
        session=session,
        settings=settings,
        metrics=metrics,
        pool=pool,
        cache=phrases,
        playback=playback,
        send=None,
    )
    tts_norm = TtsNormHandler(
        session=session,
        settings=settings,
        metrics=metrics,
        forward=audio_out,
    )
    chunker = ChunkerHandler(
        session=session,
        settings=settings,
        metrics=metrics,
        forward=tts_norm,
    )
    client = (
        llm
        if llm is not None
        else LlmClient.unavailable(
            timeout_ms=settings.llm_timeout_ms,
            max_batch=settings.llm_max_batch,
        )
    )
    handler = DialogueHandler(
        session=session,
        settings=settings,
        metrics=metrics,
        llm=client,
        forward=chunker,
        db_path=db,
        roster=names,
        now=now,
    )
    await handler.start()
    await chunker.drain()
    turns = scripted_turns(scenario, settings)
    _seed_if_book(scenario, db, turns, timezone)
    barge_hits = 0
    for index, turn in enumerate(turns):
        if scenario.barge_in and index == 0 and session.request_barge_in():
            barge_hits += 1
        audio_out.reset_play()
        session.turn_end_ts = time.monotonic()
        event = session.create_event(
            EventKind.NLU,
            {
                "spoken": turn.spoken,
                "intent": turn.intent,
                "slots": json.dumps(turn.slots),
                "nlu_ok": 1,
            },
        )
        await handler(event)
        await chunker.drain()
        if audio_out.emitted:
            audio_out.note_play_ack(0)
        if handler.machine.state.state_id in {"URGENT", "HANDOFF", "CLOSE"}:
            break
    state = handler.machine.state
    confirmed = {key: item.value for key, item in state.slots.items() if item.status == "confirmed"}
    return RunTrace(
        scenario_id=scenario.id,
        state_id=state.state_id,
        last_template=state.last_template,
        last_action=state.last_action,
        faq_chunk_id=state.faq_chunk_id,
        played_text=state.played_text,
        confirmed=confirmed,
        appointments=list_appointments(db),
        barge_in_count=float(barge_hits),
        ungrounded=0.0,
        turns=turns,
        play_emitted=audio_out.emitted,
    )
