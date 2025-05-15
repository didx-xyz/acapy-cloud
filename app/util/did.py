import re

import base58

from shared.exceptions import CloudApiValueError


def ed25519_verkey_to_did_key(key: str) -> str:
    """Convert a naked ed25519 verkey to W3C did:key format."""

    # Length validation
    if len(key) not in (43, 44):
        raise CloudApiValueError(
            "Invalid key length. ed25519 keys should be 43 or 44 characters long when base58 encoded."
        )

    # Character set validation
    if not re.match(
        "^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$", key
    ):
        raise CloudApiValueError(
            "Invalid key. ed25519 keys should only contain base58 characters."
        )

    key_bytes = base58.b58decode(key)
    prefixed_key_bytes = b"".join([b"\xed\x01", key_bytes])
    fingerprint = base58.b58encode(prefixed_key_bytes).decode("ascii")
    did_key = f"did:key:z{fingerprint}"
    return did_key


def qualified_did_sov(did: str) -> str:
    if not did.startswith("did:"):
        return f"did:sov:{did}"

    return did


def strip_qualified_did_sov(did: str) -> str:
    if did.startswith("did:sov:"):
        return did[len("did:sov:") :]

    return did


def did_from_credential_definition_id(credential_definition_id: str) -> str:
    if credential_definition_id.startswith("did:cheqd"):
        parts = credential_definition_id.split("/")
    else:  # Indy
        parts = credential_definition_id.split(":")
    return parts[0]
