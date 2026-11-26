"""Hotword lists follow expected_vocab_id. The roster is the only doctor source."""

from pathlib import Path

from nlp.hotwords import hotwords_for, load_roster


def test_vocab_lists() -> None:
    doctors = load_roster(Path("data/doctors.txt"))
    assert len(doctors) == 16
    clinic = "Turnwise Clinic"
    doctor_list = hotwords_for("doctor", clinic_name=clinic, doctors=doctors)
    assert doctor_list == list(doctors)
    date_list = hotwords_for("date", clinic_name=clinic, doctors=doctors)
    assert "tuesday" in date_list
    assert "march" in date_list
    assert doctors[0] not in date_list
    phone_list = hotwords_for("phone", clinic_name=clinic, doctors=doctors)
    for name in doctors:
        assert name not in phone_list
    greet = hotwords_for("greet", clinic_name=clinic, doctors=doctors)
    assert clinic in greet
    assert doctors[0] in greet
