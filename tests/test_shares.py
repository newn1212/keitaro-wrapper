import pytest

from app.shares import even_shares, validate_shares


@pytest.mark.parametrize("n", range(1, 15))
def test_even_shares_sum_100(n):
    assert sum(even_shares(n)) == 100


def test_even_examples():
    assert even_shares(2) == [50, 50]
    assert even_shares(3) == [34, 33, 33]


def test_validate_ok():
    validate_shares({1: 60, 2: 40}, {1, 2})


@pytest.mark.parametrize("shares", [{1: 60, 2: 30}, {1: 100}, {1: 120, 2: -20}])
def test_validate_bad(shares):
    with pytest.raises(ValueError):
        validate_shares(shares, {1, 2})
