"""DB judge covers each goal. Wrong doctor is a failure."""

from evals.harness import RunTrace
from evals.judge_db import judge
from evals.schema import Scenario
from server.config import Settings


def _scenario(**kwargs: object) -> Scenario:
    payload = {
        "id": "t",
        "goal": "book",
        "intent": "book",
        "slots": {
            "patient_name": "Ada Lovelace",
            "phone": "5550100123",
            "doctor": "Dr. Avery Lang",
            "date": "2026-12-15",
            "time": "15:00",
        },
        "persona": "brief",
        "speaking_rate": 1.0,
        "disfluency": False,
        "barge_in": False,
        "urgent": False,
        "clock": "virtual",
        "caller": "scripted",
        "script": ["yes"],
    }
    payload.update(kwargs)
    return Scenario.model_validate(payload)


def _trace(**kwargs: object) -> RunTrace:
    base = RunTrace(
        scenario_id="t",
        state_id="CLOSE",
        last_template="booked",
        last_action="say_done",
        faq_chunk_id="",
        played_text="",
        confirmed={},
        appointments=[],
        barge_in_count=0.0,
        ungrounded=0.0,
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_wrong_doctor_is_failure() -> None:
    scenario = _scenario()
    trace = _trace(
        appointments=[
            {
                "id": "A1",
                "doctor_id": "Dr. Khan",
                "start_iso": "2026-12-15T15:00:00-05:00",
                "status": "booked",
                "slots_json": '{"doctor": "Dr. Khan"}',
            }
        ]
    )
    judged = judge(scenario, trace, settings=Settings())
    assert judged.success is False
    assert judged.reason == "wrong_doctor"


def test_urgent_with_no_row() -> None:
    scenario = _scenario(goal="urgent", intent="urgent_symptom", slots={}, script=["can't breathe"])
    trace = _trace(state_id="URGENT", last_template="seek_emergency")
    judged = judge(scenario, trace)
    assert judged.success is True


def test_faq_hours_needs_chunk() -> None:
    scenario = _scenario(
        goal="faq",
        intent="faq",
        slots={"faq_query": "what are your hours"},
        script=["what are your hours"],
    )
    miss = _trace(state_id="FAQ", last_template="faq_refuse", last_action="say_faq_refuse")
    assert judge(scenario, miss).success is False
    hit = _trace(
        state_id="FAQ",
        last_template="faq",
        last_action="say_faq",
        faq_chunk_id="hours",
        played_text="hours: open",
    )
    judged = judge(scenario, hit)
    assert judged.success is True


def test_faq_unknown_is_refusal() -> None:
    scenario = _scenario(
        goal="faq",
        intent="faq",
        slots={"faq_query": "zyzzyva xylophone"},
        script=["zyzzyva xylophone"],
    )
    refuse = _trace(state_id="FAQ", last_template="faq_refuse", last_action="say_faq_refuse")
    assert judge(scenario, refuse).success is True
    fake = _trace(
        state_id="FAQ",
        last_template="faq",
        last_action="say_faq",
        faq_chunk_id="",
        ungrounded=1.0,
    )
    assert judge(scenario, fake).success is False


def test_handoff_and_cancel_and_check() -> None:
    handoff = judge(
        _scenario(goal="handoff", intent="speak_to_human", slots={}),
        _trace(state_id="HANDOFF", last_template="handoff_summary"),
    )
    assert handoff.success is True
    cancel = judge(
        _scenario(goal="cancel", intent="cancel", slots={}),
        _trace(
            appointments=[
                {
                    "id": "A1",
                    "doctor_id": "Dr. Avery Lang",
                    "start_iso": "x",
                    "status": "cancelled",
                    "slots_json": "{}",
                }
            ]
        ),
    )
    assert cancel.success is True
    check = judge(
        _scenario(goal="check", intent="check_appointment", slots={}),
        _trace(
            appointments=[
                {
                    "id": "A1",
                    "doctor_id": "Dr. Avery Lang",
                    "start_iso": "x",
                    "status": "booked",
                    "slots_json": "{}",
                }
            ]
        ),
    )
    assert check.success is True


def test_yes_to_wrong_readback_fails_even_if_sqlite_matches_wrong() -> None:
    scenario = _scenario()
    trace = _trace(
        confirmed={"doctor": "Dr. Khan"},
        appointments=[
            {
                "id": "A1",
                "doctor_id": "Dr. Khan",
                "start_iso": "2026-12-15T15:00:00-05:00",
                "status": "booked",
                "slots_json": '{"doctor": "Dr. Khan"}',
            }
        ],
    )
    judged = judge(scenario, trace, settings=Settings())
    assert judged.success is False
