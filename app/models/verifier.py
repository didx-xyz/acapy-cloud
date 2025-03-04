from enum import Enum
from typing import Optional, Union

from aries_cloudcontroller import (
    AnoncredsPresentationRequest,
    DIFPresSpec,
    DIFProofRequest,
    IndyNonRevocationInterval,
    IndyPresSpec,
)
from aries_cloudcontroller import IndyProofRequest as AcaPyIndyProofRequest
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from app.util.save_exchange_record import SaveExchangeRecordField
from shared.exceptions import CloudApiValueError


class ProofRequestType(str, Enum):
    INDY: str = "indy"
    JWT: str = "jwt"
    LD_PROOF: str = "ld_proof"
    ANONCREDS: str = "anoncreds"


class IndyProofRequest(AcaPyIndyProofRequest):
    name: str = Field(default="Proof", description="Proof request name")
    version: str = Field(default="1.0", description="Proof request version")


class ProofRequestBase(BaseModel):
    type: ProofRequestType = ProofRequestType.INDY
    indy_proof_request: Optional[IndyProofRequest] = None
    dif_proof_request: Optional[DIFProofRequest] = None
    anoncreds_proof_request: Optional[AnoncredsPresentationRequest] = None

    @model_validator(mode="before")
    @classmethod
    def check_proof_request(cls, values: Union[dict, "ProofRequestBase"]):
        # pydantic v2 removed safe way to get key, because `values` can be a dict or this type
        if not isinstance(values, dict):
            values = values.__dict__

        proof_type = values.get("type")
        indy_proof = values.get("indy_proof_request")
        dif_proof = values.get("dif_proof_request")
        anoncreds_proof = values.get("anoncreds_proof_request")

        if proof_type == ProofRequestType.ANONCREDS and anoncreds_proof is None:
            raise CloudApiValueError(
                "anoncreds_proof_request must be populated if `anoncreds` type is selected"
            )

        if proof_type == ProofRequestType.INDY and indy_proof is None:
            raise CloudApiValueError(
                "indy_proof_request must be populated if `indy` type is selected"
            )

        if proof_type == ProofRequestType.LD_PROOF and dif_proof is None:
            raise CloudApiValueError(
                "dif_proof_request must be populated if `ld_proof` type is selected"
            )

        if proof_type == ProofRequestType.INDY and (
            dif_proof is not None or anoncreds_proof is not None
        ):
            raise CloudApiValueError(
                "Only indy_proof_request must not be populated if `indy` type is selected"
            )

        if proof_type == ProofRequestType.LD_PROOF and (
            indy_proof is not None or anoncreds_proof is not None
        ):
            raise CloudApiValueError(
                "Only dif_proof_request must not be populated if `ld_proof` type is selected"
            )

        if proof_type == ProofRequestType.ANONCREDS and (
            indy_proof is not None or dif_proof is not None
        ):
            raise CloudApiValueError(
                "Only anoncreds_proof_request must not be populated if `anoncreds` type is selected"
            )

        return values


class ProofRequestMetadata(BaseModel):
    comment: Optional[str] = None


class CreateProofRequest(
    ProofRequestBase, ProofRequestMetadata, SaveExchangeRecordField
):
    pass


class SendProofRequest(CreateProofRequest):
    connection_id: str


class ProofId(BaseModel):
    proof_id: str


class AcceptProofRequest(ProofId, SaveExchangeRecordField):
    type: ProofRequestType = ProofRequestType.INDY
    indy_presentation_spec: Optional[IndyPresSpec] = None
    dif_presentation_spec: Optional[DIFPresSpec] = None

    @field_validator("indy_presentation_spec", mode="before")
    @classmethod
    def check_indy_presentation_spec(cls, value, values: ValidationInfo):
        if values.data.get("type") == ProofRequestType.INDY and value is None:
            raise CloudApiValueError(
                "indy_presentation_spec must be populated if `indy` type is selected"
            )
        return value

    @field_validator("dif_presentation_spec", mode="before")
    @classmethod
    def check_dif_presentation_spec(cls, value, values: ValidationInfo):
        if values.data.get("type") == ProofRequestType.LD_PROOF and value is None:
            raise CloudApiValueError(
                "dif_presentation_spec must be populated if `ld_proof` type is selected"
            )
        return value


class RejectProofRequest(ProofId):
    problem_report: str = Field(
        default="Rejected",
        description="Message to send with the rejection",
    )
    delete_proof_record: bool = Field(
        default=False,
        description=(
            "(True) delete the proof exchange record after rejecting, or "
            "(default, False) preserve the record after rejecting"
        ),
    )

    @field_validator("problem_report", mode="before")
    @classmethod
    def validate_problem_report(cls, value):
        if value == "":
            raise CloudApiValueError("problem_report cannot be an empty string")
        return value


class CredInfo(BaseModel):
    attrs: dict = Field(default=None, description="Attribute names and value")
    cred_def_id: str = Field(
        default=None, description="Credential definition identifier"
    )
    referent: str = Field(default=None, description="Credential identifier")
    credential_id: str = Field(default=None, description="Credential identifier")
    cred_rev_id: Optional[str] = Field(
        default=None, description="Credential revocation identifier"
    )
    rev_reg_id: Optional[str] = Field(
        default=None, description="Revocation registry identifier"
    )
    schema_id: Optional[str] = Field(default=None, description="Schema identifier")


class CredPrecis(BaseModel):
    cred_info: CredInfo = Field(description="Credential info")
    interval: Optional[IndyNonRevocationInterval] = Field(
        default=None, description="Non-revocation interval from presentation request"
    )
    presentation_referents: Optional[list] = Field(
        default=None, description="Presentation referents"
    )
