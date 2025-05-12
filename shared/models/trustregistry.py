from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shared.exceptions import CloudApiValueError

TrustRegistryRole = Literal["issuer", "verifier"]


class Actor(BaseModel):
    id: str
    name: str
    roles: List[TrustRegistryRole]
    did: str
    didcomm_invitation: Optional[str] = None
    image_url: Optional[str] = None

    @field_validator("did")
    @classmethod
    def did_validator(cls, did: str):
        if not did.startswith("did:"):
            raise CloudApiValueError("Only fully qualified DIDs allowed.")

        return did

    model_config = ConfigDict(validate_assignment=True, from_attributes=True)


def calc_schema_id(did: str, name: str, version: str) -> str:
    return f"{did}:2:{name}:{version}"


class Schema(BaseModel):
    did: str = Field(default=None)
    name: str = Field(default=None)
    version: str = Field(default=None)
    id: str = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def validate_and_set_values(cls, values: Union[dict, "Schema"]):
        # pydantic v2 removed safe way to get key, because `values` can be a dict or this type
        if not isinstance(values, dict):
            values = values.__dict__

        try:
            id = values["id"]
        except KeyError:
            id = None

        cheqd_did = False
        if id and id.startswith("did:cheqd:"):
            cheqd_did = True

        try:
            for v in ["did", "name", "version"]:
                if not cheqd_did and ":" in values[v]:
                    raise CloudApiValueError(
                        f"Schema field `{v}` must not contain colon."
                    )
            did = values["did"]
            name = values["name"]
            version = values["version"]
        except KeyError:
            did = None
            name = None
            version = None

        if cheqd_did:
            did = id.split("/")[0]
            version = "1.0.0"
            name = "Cheqd-LinkedResource"
        else:
            if id is None:
                if None in (did, name, version):
                    raise CloudApiValueError(
                        "Either `id` or all of (`did`, `name`, `version`) must be specified."
                    )
                id = calc_schema_id(did, name, version)
            else:
                if None not in (did, name, version):
                    expected_id = calc_schema_id(did, name, version)
                    if id != expected_id:
                        raise CloudApiValueError(
                            f"Schema's `id` field does not match expected format: `{expected_id}`."
                        )
                else:
                    # Extract did, name, and version from id if not specified
                    try:
                        did, _, name, version = id.split(":")
                    except ValueError as e:
                        raise CloudApiValueError(
                            "Invalid `id` field. It does not match the expected format."
                        ) from e

        values["did"] = did
        values["name"] = name
        values["version"] = version
        values["id"] = id
        return values

    model_config = ConfigDict(validate_assignment=True, from_attributes=True)
