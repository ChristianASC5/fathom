# One of these fails on purpose, so a prediction about the run can be wrong.
# Named check_*.py so no other project's pytest collects it.
from chunks import chunk


def test_even_split():
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def test_remainder():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def test_empty():
    assert chunk([], 3) == []
