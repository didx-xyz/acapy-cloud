from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from shared.log_config import get_logger
from shared.models.trustregistry import Schema
from trustregistry import crud
from trustregistry.db import get_db

logger = get_logger(__name__)

router = APIRouter(prefix="/registry/schemas", tags=["schema"])


class SchemaID(BaseModel):
    schema_id: str = Field(..., examples=["WgWxqztrNooG92RXvxSTWv:2:schema_name:1.0"])


@router.get("", response_model=List[Schema])
async def get_schemas(db_session: Session = Depends(get_db)) -> List[Schema]:
    logger.debug("GET request received: Fetch all schemas")
    db_schemas = crud.get_schemas(db_session)

    return db_schemas


@router.post("", response_model=Schema)
async def register_schema(
    schema_id: SchemaID, db_session: Session = Depends(get_db)
) -> Schema:
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.debug("POST request received: Register schema")
    schema_attrs_list = _get_schema_attrs(schema_id)
    try:
        if schema_attrs_list:
            schema = Schema(
                did=schema_attrs_list[0],
                name=schema_attrs_list[2],
                version=schema_attrs_list[3],
                id=schema_id.schema_id,
            )
        else:
            # did:cheqd schema
            schema = Schema(
                id=schema_id.schema_id,
            )

        create_schema_res = crud.create_schema(
            db_session,
            schema=schema,
        )
    except crud.SchemaAlreadyExistsException as e:
        bound_logger.info("Bad request: Schema already exists.")
        raise HTTPException(status_code=409, detail="Schema already exists.") from e

    return create_schema_res


@router.put("/{schema_id}", response_model=Schema)
async def update_schema(
    schema_id: str, new_schema_id: SchemaID, db_session: Session = Depends(get_db)
) -> Schema:
    bound_logger = logger.bind(
        body={"schema_id": schema_id, "new_schema_id": new_schema_id}
    )
    bound_logger.debug("PUT request received: Update schema")
    if schema_id == new_schema_id.schema_id:
        bound_logger.info("Bad request: New schema ID is identical to existing one.")
        raise HTTPException(
            status_code=400,
            detail="New schema ID is identical to the existing one. "
            "Update operation expects a different schema ID.",
        )

    schema_attrs_list = _get_schema_attrs(new_schema_id)

    new_schema = Schema(
        did=schema_attrs_list[0],
        name=schema_attrs_list[2],
        version=schema_attrs_list[3],
        id=new_schema_id.schema_id,
    )

    try:
        update_schema_res = crud.update_schema(
            db_session,
            schema=new_schema,
            schema_id=schema_id,
        )
    except crud.SchemaDoesNotExistException as e:
        bound_logger.info("Bad request: Schema with id not found.")
        raise HTTPException(
            status_code=405,
            detail="Schema not found.",
        ) from e

    return update_schema_res


@router.get("/{schema_id:path}", response_model=Schema)
async def get_schema(schema_id: str, db_session: Session = Depends(get_db)) -> Schema:
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.debug("GET request received: Fetch schema")
    try:
        schema = crud.get_schema_by_id(db_session, schema_id=schema_id)
    except crud.SchemaDoesNotExistException as e:
        bound_logger.info("Bad request: Schema with id not found.")
        raise HTTPException(
            status_code=404,
            detail=f"Schema with id {schema_id} not found.",
        ) from e

    return schema


@router.delete("/{schema_id}", status_code=204)
async def remove_schema(schema_id: str, db_session: Session = Depends(get_db)) -> None:
    bound_logger = logger.bind(body={"schema_id": schema_id})
    bound_logger.debug("DELETE request received: Delete schema")
    try:
        crud.delete_schema(db_session, schema_id=schema_id)
    except crud.SchemaDoesNotExistException as e:
        bound_logger.info("Bad request: Schema with id not found.")
        raise HTTPException(
            status_code=404,
            detail="Schema not found.",
        ) from e


def _get_schema_attrs(schema_id: SchemaID) -> List[str]:
    # Split from the back because DID may contain a colon
    if schema_id.schema_id.startswith("did:cheqd:"):
        return []
    return schema_id.schema_id.split(":", 3)
