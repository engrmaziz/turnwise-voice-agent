"""LocalAgreement-2 commits only after two consecutive hypotheses agree."""

from nlp.local_agreement import LocalAgreement2, local_agreement_2


def test_second_call_commits_shared_prefix() -> None:
    agreement = LocalAgreement2()
    assert agreement.push("book tue") == ""
    assert agreement.push("book tuesday at") == "book "


def test_rewrite_of_the_first_word_commits_nothing() -> None:
    agreement = LocalAgreement2()
    assert agreement.push("book tue") == ""
    assert agreement.push("schedule tuesday") == ""
    assert local_agreement_2("book tue", "schedule tuesday") == ""
