"""Base62 encoding and decoding utilities."""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE = len(ALPHABET)
_DECODE_MAP = {character: value for value, character in enumerate(ALPHABET)}


def encode(num: int) -> str:
    """Encode a non-negative integer as a Base62 string."""
    if num < 0:
        raise ValueError("num must be non-negative")
    if num == 0:
        return ALPHABET[0]

    digits: list[str] = []
    while num:
        num, remainder = divmod(num, _BASE)
        digits.append(ALPHABET[remainder])
    return "".join(reversed(digits))


def decode(s: str) -> int:
    """Decode a Base62 string into a non-negative integer."""
    if not s:
        raise ValueError("s must not be empty")

    value = 0
    for character in s:
        try:
            digit = _DECODE_MAP[character]
        except KeyError as error:
            raise ValueError(f"invalid Base62 character: {character!r}") from error
        value = value * _BASE + digit
    return value