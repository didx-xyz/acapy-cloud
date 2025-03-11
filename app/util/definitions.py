from aries_cloudcontroller import CredentialDefinition as AcaPyCredentialDefinition
from aries_cloudcontroller import (
    GetCredDefResult,
    GetSchemaResult,
    ModelSchema,
    SchemaState,
)

from app.models.definitions import CredentialDefinition, CredentialSchema


def anoncreds_credential_schema(schema: SchemaState):
    return CredentialSchema(
        id=schema.schema_id,
        name=schema.var_schema.name,
        version=schema.var_schema.version,
        attribute_names=schema.var_schema.attr_names,
    )


def credential_schema_from_acapy(schema: ModelSchema):
    return CredentialSchema(
        id=schema.id,
        name=schema.name,
        version=schema.version,
        attribute_names=schema.attr_names,
    )


def anoncreds_schema_from_acapy(schema: GetSchemaResult):
    return CredentialSchema(
        id=schema.schema_id,
        attribute_names=schema.var_schema.attr_names,
        name=schema.var_schema.name,
        version=schema.var_schema.version,
    )


def credential_definition_from_acapy(
    credential_definition: GetCredDefResult | AcaPyCredentialDefinition,
):
    if isinstance(credential_definition, GetCredDefResult):
        # Anoncreds Cred Def
        return CredentialDefinition(
            id=credential_definition.credential_definition_id,
            tag=credential_definition.credential_definition.tag,
            schema_id=credential_definition.credential_definition.schema_id,
        )
    else:
        # Indy Cred Def
        return CredentialDefinition(
            id=credential_definition.id,
            tag=credential_definition.tag,
            schema_id=credential_definition.schema_id,
        )
