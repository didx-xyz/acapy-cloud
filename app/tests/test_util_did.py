import pytest

from app.util.did import ed25519_verkey_to_did_key
from shared.exceptions import CloudApiValueError


def test_ed25519_verkey_to_did_key() -> None:
    verkey = "8HH5gYEeNc3z7PYXmd54d4x6qAfCNrqQqEB3nS7Zfu7K"
    did_key = "did:key:z6MkmjY8GnV5i9YTDtPETC2uUAW6ejw3nk5mXF5yci5ab7th"

    assert ed25519_verkey_to_did_key(verkey) == did_key

    # Test valid keys of length 43 and 44
    for valid_key in [
        "abcdefghijkmnopqrstuvwxyz123456789ABCDEFGHJ",  # length 43
        "abcdefghijkmnopqrstuvwxyz123456789ABCDEFGHJK",  # length 44
    ]:
        assert ed25519_verkey_to_did_key(valid_key).startswith("did:key:z")

    # Test invalid key lengths
    with pytest.raises(CloudApiValueError, match="Invalid key length."):
        ed25519_verkey_to_did_key(
            "abcdefghijkmnopqrstuvwxyz123456789ABCDEFGH"
        )  # length 42
    with pytest.raises(CloudApiValueError, match="Invalid key length."):
        ed25519_verkey_to_did_key(
            "abcdefghijkmnopqrstuvwxyz123456789ABCDEFGHJKL"
        )  # length 45

    # Test invalid characters
    with pytest.raises(CloudApiValueError, match="Invalid key."):
        ed25519_verkey_to_did_key(
            "abcdefghijkmnopqrstuvwxyz123456789ABCDEFGH*"
        )  # invalid character *
    with pytest.raises(CloudApiValueError, match="Invalid key."):
        ed25519_verkey_to_did_key(
            "abcdefghijkmnopqrstuvwxyz123456789ABCDEFGHJ0"
        )  # invalid character 0
