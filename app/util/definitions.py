from aries_cloudcontroller import (
    GetCredDefResult,
    GetSchemaResult,
    ModelSchema,
    SchemaState,
)

from app.models.definitions import CredentialDefinition, CredentialSchema
from shared.log_config import get_logger

logger = get_logger(__name__)


def anoncreds_credential_schema(schema: SchemaState) -> CredentialSchema:
    if not schema.schema_id or not schema.var_schema:  # pragma: no cover
        logger.error("Schema is missing required fields: {}", schema)
        raise ValueError(f"Schema is missing required fields: {schema}")

    return CredentialSchema(
        id=schema.schema_id,
        name=schema.var_schema.name,
        version=schema.var_schema.version,
        attribute_names=schema.var_schema.attr_names,
    )


def credential_schema_from_acapy(schema: ModelSchema) -> CredentialSchema:
    if (
        not schema.id or not schema.name or not schema.version or not schema.attr_names
    ):  # pragma: no cover
        logger.error("Schema is missing required fields: {}", schema)
        raise ValueError(f"Schema is missing required fields: {schema}")

    return CredentialSchema(
        id=schema.id,
        name=schema.name,
        version=schema.version,
        attribute_names=schema.attr_names,
    )


def anoncreds_schema_from_acapy(schema: GetSchemaResult) -> CredentialSchema:
    if not schema.schema_id or not schema.var_schema:  # pragma: no cover
        logger.error("Schema is missing required fields: {}", schema)
        raise ValueError(f"Schema is missing required fields: {schema}")

    return CredentialSchema(
        id=schema.schema_id,
        attribute_names=schema.var_schema.attr_names,
        name=schema.var_schema.name,
        version=schema.var_schema.version,
    )


def credential_definition_from_acapy(
    cred_def_result: GetCredDefResult,
) -> CredentialDefinition:
    cred_def_id = cred_def_result.credential_definition_id
    cred_def = cred_def_result.credential_definition
    if (
        not cred_def_id or not cred_def or not cred_def.tag or not cred_def.schema_id
    ):  # pragma: no cover
        logger.error(
            "Credential definition is missing required fields: {}",
            cred_def_result,
        )
        raise ValueError(
            f"Credential definition is missing required fields: {cred_def_result}"
        )

    return CredentialDefinition(
        id=cred_def_id,
        tag=cred_def.tag,
        schema_id=cred_def.schema_id,
    )
