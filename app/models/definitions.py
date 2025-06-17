from enum import Enum

from pydantic import BaseModel, Field

sample_schema_id = "CXQseFxV34pcb8vf32XhEa:2:test_schema:0.3"
sample_tag = "default"
sample_credential_definition_id = "5Q1Zz9foMeAA8Q7mrmzCfZ:3:CL:7:default"
sample_name = "test_schema"
sample_version = "0.3"
sample_attribute_names = ["name", "age"]


class SchemaType(str, Enum):
    ANONCREDS = "anoncreds"


class CreateCredentialDefinition(BaseModel):
    schema_id: str = Field(..., examples=[sample_schema_id])
    tag: str = Field(..., examples=[sample_tag])
    support_revocation: bool = Field(default=False)


class CredentialDefinition(BaseModel):
    id: str = Field(..., examples=[sample_credential_definition_id])
    tag: str = Field(..., examples=[sample_tag])
    schema_id: str = Field(..., examples=[sample_schema_id])


class CreateSchema(BaseModel):
    schema_type: SchemaType = Field(
        default=SchemaType.ANONCREDS,
        description="The type of schema to create. Currently only 'anoncreds' is supported.",
    )
    name: str = Field(..., examples=[sample_name])
    version: str = Field(..., examples=[sample_version])
    attribute_names: list[str] = Field(..., examples=[sample_attribute_names])


class CredentialSchema(BaseModel):
    id: str = Field(..., examples=[sample_schema_id])
    name: str = Field(..., examples=[sample_name])
    version: str = Field(..., examples=[sample_version])
    attribute_names: list[str] = Field(..., examples=[sample_attribute_names])
