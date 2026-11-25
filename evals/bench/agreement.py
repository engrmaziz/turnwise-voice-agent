"""LocalAgreement-2: the prefix two consecutive hypotheses share."""


def local_agreement_2(first: str, second: str) -> str:
    """Word-wise longest common prefix. Empty if the first words differ."""
    left = first.split()
    right = second.split()
    shared = 0
    limit = min(len(left), len(right))
    while shared < limit and left[shared] == right[shared]:
        shared += 1
    return " ".join(left[:shared])
