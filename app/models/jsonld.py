from typing import Any

from aries_cloudcontroller import SignatureOptions
from pydantic import BaseModel, model_validator

from shared.exceptions.cloudapi_value_error import CloudApiValueError


class JsonLdSignRequest(BaseModel):
    credential_id: str | None = None
    credential: dict[str, Any] | None = None
    verkey: str | None = None
    pub_did: str | None = None
    signature_options: SignatureOptions

    @model_validator(mode="before")
    @classmethod
    def validate_credential_provided(cls, values: dict) -> dict:
        cred, cred_id = values.get("credential"), values.get("credential_id")
        if not cred and not cred_id:
            raise CloudApiValueError(
                "At least one of `credential` or `credential_id` must be provided."
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_not_both_verkey_and_pub_did(cls, values: dict) -> dict:
        verkey, pub_did = values.get("verkey"), values.get("pub_did")
        if verkey and pub_did:
            raise CloudApiValueError(
                "Please provide either or neither, but not both, the pub_did or the verkey for the document.",
            )
        return values


class JsonLdVerifyRequest(BaseModel):
    doc: dict[str, Any]
    public_did: str | None = None
    verkey: str | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_not_both_verkey_and_pub_did(cls, values: dict) -> dict:
        verkey, pub_did = values.get("verkey"), values.get("public_did")
        if verkey and pub_did:
            raise CloudApiValueError(
                "Please provide either or neither, but not both, the public_did or the verkey for the document.",
            )
        return values
