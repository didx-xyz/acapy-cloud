from aries_cloudcontroller import CredentialDefinition as AcaPyCredentialDefinition
from aries_cloudcontroller import SchemaState, GetSchemaResult

from app.models.definitions import CredentialDefinition, CredentialSchema


def credential_schema_from_acapy(schema: SchemaState):
    return CredentialSchema(
        id=schema.schema_id,
        name=schema.var_schema.name,
        version=schema.var_schema.version,
        attribute_names=schema.var_schema.attr_names,
    )


def credential_definition_from_acapy(credential_definition: AcaPyCredentialDefinition):
    return CredentialDefinition(
        id=credential_definition.id,
        tag=credential_definition.tag,
        schema_id=credential_definition.schema_id,
    )


def schema_from_acapy(schema: GetSchemaResult):
    return CredentialSchema(
        id=schema.schema_id,
        attribute_names=schema.var_schema.attr_names,
        name=schema.var_schema.name,
        version=schema.var_schema.version,
    )
