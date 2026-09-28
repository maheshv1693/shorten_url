"""Tests for Base62 encoding and decoding."""

import pytest

from app.core.base62 import decode, encode


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (0, "0"),
        (1, "1"),
        (61, "Z"),
        (62, "10"),
        (125, "21"),
        (1_000_000, "4c92"),
    ],
)
def test_encode_known_values(number: int, expected: str) -> None:
    """Encoding maps integers to their expected Base62 representations."""
    assert encode(number) == expected


@pytest.mark.parametrize("number", [0, 1, 61, 62, 125, 3_844, 1_000_000, 2**128])
def test_encode_decode_round_trip(number: int) -> None:
    """Decoding an encoded integer returns the original value."""
    assert decode(encode(number)) == number


def test_encode_rejects_negative_number() -> None:
    """Negative integers cannot be represented by this Base62 format."""
    with pytest.raises(ValueError):
        encode(-1)


@pytest.mark.parametrize("value", ["", "-", "@", "!"])
def test_decode_rejects_empty_or_invalid_strings(value: str) -> None:
    """Empty strings and characters outside the alphabet are rejected."""
    with pytest.raises(ValueError):
        decode(value)