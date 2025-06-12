import base64
import json
import random
import string
from random import randint


def random_string(length: int) -> str:
    letters = string.ascii_uppercase
    return "".join(random.choice(letters) for _ in range(length))


def pad(val: str) -> str:
    """Pad base64 values if need be: JWT calls to omit trailing padding."""
    pad_length = 4 - len(val) % 4
    return val if pad_length > 2 else (val + "=" * pad_length)


def base64_to_json(value: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(pad(value)).decode("utf-8"))


def random_version() -> str:
    return f"{randint(1, 100)}.{randint(1, 100)}.{randint(1, 100)}"
