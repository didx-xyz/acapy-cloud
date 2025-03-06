from aries_cloudcontroller import CredentialDefinition as AcaPyCredentialDefinition
from aries_cloudcontroller import GetSchemaResult, ModelSchema, SchemaState

from app.models.definitions import CredentialDefinition, CredentialSchema


def credential_anon_schema_from_acapy(schema: SchemaState):
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


def anon_schema_from_acapy(schema: GetSchemaResult):
    return CredentialSchema(
        id=schema.schema_id,
        attribute_names=schema.var_schema.attr_names,
        name=schema.var_schema.name,
        version=schema.var_schema.version,
    )


def credential_definition_from_acapy(credential_definition: AcaPyCredentialDefinition):
    return CredentialDefinition(
        id=credential_definition.id,
        tag=credential_definition.tag,
        schema_id=credential_definition.schema_id,
    )
