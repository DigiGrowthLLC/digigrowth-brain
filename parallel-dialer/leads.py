"""Phone number normalisation helper used across the dialer."""


def _norm(phone):
    return str(phone).replace("+", "").replace(" ", "").replace("-", "")
