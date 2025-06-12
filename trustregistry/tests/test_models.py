import pytest

from shared.exceptions.cloudapi_value_error import CloudApiValueError
from shared.models.trustregistry import Actor, Schema
from trustregistry import db


def test_actor() -> None:
    actor = Actor(
        id="mickey-mouse",
        name="Mickey Mouse",
        roles=["verifier", "issuer"],
        didcomm_invitation="xyz",
        did="did:key:abc",
    )

    assert actor.id == "mickey-mouse"
    assert actor.name == "Mickey Mouse"
    assert actor.roles == ["verifier", "issuer"]
    assert actor.didcomm_invitation == "xyz"
    assert actor.did == "did:key:abc"


def test_schema() -> None:
    schema = Schema(did="abc", name="schema", version="0.4.20")

    assert schema.did == "abc"
    assert schema.name == "schema"
    assert schema.version == "0.4.20"
    assert schema.id == "abc:2:schema:0.4.20"

    with pytest.raises(CloudApiValueError):
        Schema(did="abc:def", name="schema", version="0.4.20")

    with pytest.raises(CloudApiValueError):
        Schema(did="abc", name="double:ace:schema", version="0.4.20")

    with pytest.raises(CloudApiValueError):
        Schema(did="abc", name="schema", version="0:4:20")


def test_db_actor() -> None:
    actor = db.Actor(
        id="mickey-mouse",
        name="Mickey Mouse",
        roles="verifier, issuer",
        didcomm_invitation="xyz",
        did="abc",
    )

    assert actor.id == "mickey-mouse"
    assert actor.name == "Mickey Mouse"
    assert actor.roles == "verifier, issuer"
    assert actor.didcomm_invitation == "xyz"
    assert actor.did == "abc"


def test_db_schema() -> None:
    schema = db.Schema(did="abc", name="schema", version="0.4.20")

    assert schema.did == "abc"
    assert schema.name == "schema"
    assert schema.version == "0.4.20"
