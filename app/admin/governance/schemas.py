from typing import List, Optional

from aries_cloudcontroller import AriesAgentControllerBase
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dependencies import yoma_agent

router = APIRouter(prefix="/admin/governance/schemas", tags=["Admin: Schemas"])


class SchemaDefinition(BaseModel):
    name: str
    version: str
    attributes: List[str]


@router.get("/{schema_id}")
async def get_schema(
    schema_id: str,
    aries_controller: AriesAgentControllerBase = Depends(yoma_agent),
):
    return await aries_controller.schema.get_by_id(schema_id=schema_id)


@router.get("/")
async def get_schemas(
    schema_id: Optional[str] = None,
    schema_issuer_did: Optional[str] = None,
    schema_name: Optional[str] = None,
    schema_version: Optional[str] = None,
    aries_controller: AriesAgentControllerBase = Depends(yoma_agent),
):
    return await aries_controller.schema.get_created_schema(
        schema_id=schema_id,
        schema_issuer_did=schema_issuer_did,
        schema_name=schema_name,
        schema_version=schema_version,
    )


@router.post("/")
async def create_schema(
    schema_definition: SchemaDefinition,
    aries_controller: AriesAgentControllerBase = Depends(yoma_agent),
):
    schema_definition = await aries_controller.schema.write_schema(
        schema_definition.name, schema_definition.attributes, schema_definition.version
    )
    return schema_definition
