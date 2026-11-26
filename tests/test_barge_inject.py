"""Barge-in injection moves the session generation when the fixture is labeled."""

from pathlib import Path

from evals.barge_inject import inject_barge
from evals.schema import load_scenario
from tests.conftest import Harness


def test_barge_inject_moves_counter_when_labeled(harness: Harness) -> None:
    scenario = load_scenario(Path("evals/scenarios/examples/barge_mid_confirm.yaml"))
    harness.session.barge_in_enabled = True
    before = harness.session.generation
    assert inject_barge(harness.session, scenario) is True
    assert harness.session.generation == before + 1


def test_unlabeled_fixture_does_not_barge(harness: Harness) -> None:
    scenario = load_scenario(Path("evals/scenarios/examples/book_happy.yaml"))
    harness.session.barge_in_enabled = True
    before = harness.session.generation
    assert inject_barge(harness.session, scenario) is False
    assert harness.session.generation == before
