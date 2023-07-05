import pytest

from trustregistry.schemas import Actor, Schema


def test_actor():
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


def test_schema():
    schema = Schema(did="abc", name="doubleaceschema", version="0.4.20")

    assert schema.did == "abc"
    assert schema.name == "doubleaceschema"
    assert schema.version == "0.4.20"
    assert schema.id == "abc:2:doubleaceschema:0.4.20"

    with pytest.raises(ValueError):
        Schema(did="abc:def", name="doubleaceschema", version="0.4.20")

    with pytest.raises(ValueError):
        Schema(did="abc", name="double:ace:schema", version="0.4.20")

    with pytest.raises(ValueError):
        Schema(did="abc", name="doubleaceschema", version="0:4:20")
