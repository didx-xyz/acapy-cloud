from aries_cloudcontroller import CredDef, GetCredDefResult, ModelSchema

from app.util.definitions import (
    credential_definition_from_acapy,
    credential_schema_from_acapy,
)


def test_credential_schema_from_acapy():
    acapy_schema = ModelSchema(
        attr_names=["first", "second"],
        id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.1",
        seq_no=100,
        name="the_name",
        ver="1.0",
        version="1.0",
    )

    schema = credential_schema_from_acapy(acapy_schema)

    assert schema.model_dump() == {
        "id": acapy_schema.id,
        "name": acapy_schema.name,
        "version": acapy_schema.version,
        "attribute_names": acapy_schema.attr_names,
    }


def test_credential_definition_from_acapy():
    acapy_cred_def = GetCredDefResult(
        credential_definition_id="WgWxqztrNooG92RXvxSTWv:3:CL:20:tag2",
        credential_definition=CredDef(
            tag="the_tag",
            schema_id="WgWxqztrNooG92RXvxSTWv:2:schema_name:1.1",
        ),
    )

    cred_def = credential_definition_from_acapy(acapy_cred_def)

    assert cred_def.model_dump() == {
        "id": acapy_cred_def.credential_definition_id,
        "schema_id": acapy_cred_def.credential_definition.schema_id,
        "tag": acapy_cred_def.credential_definition.tag,
    }
