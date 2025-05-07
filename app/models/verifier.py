from typing import Optional, Union

from aries_cloudcontroller import (
    AnonCredsPresentationRequest as AcaPyAnonCredsPresentationRequest,
)
from aries_cloudcontroller import (
    AnonCredsPresSpec,
    DIFPresSpec,
    DIFProofRequest,
    IndyNonRevocationInterval,
    IndyPresSpec,
)
from aries_cloudcontroller import IndyProofRequest as AcaPyIndyProofRequest
from pydantic import BaseModel, Field, field_validator, model_validator

from app.util.save_exchange_record import SaveExchangeRecordField
from shared.exceptions import CloudApiValueError


class AnonCredsPresentationRequest(AcaPyAnonCredsPresentationRequest):
    name: str = Field(default="Proof", description="Proof request name")
    version: str = Field(default="1.0", description="Proof request version")


class ProofRequestBase(BaseModel):
    anoncreds_proof_request: Optional[AnonCredsPresentationRequest] = None
    dif_proof_request: Optional[DIFProofRequest] = None

    @model_validator(mode="before")
    @classmethod
    def check_proof_request(cls, values: Union[dict, "ProofRequestBase"]):
        # pydantic v2 removed safe way to get key, because `values` can be a dict or this type
        if not isinstance(values, dict):
            values = values.__dict__

        dif_proof = values.get("dif_proof_request")
        anoncreds_proof = values.get("anoncreds_proof_request")

        if anoncreds_proof is None and dif_proof is None:
            raise CloudApiValueError(
                "One of anoncreds_proof_request or dif_proof_request must be populated"
            )

        if anoncreds_proof is not None and dif_proof is not None:
            raise CloudApiValueError(
                "Only one of dif_proof_request or anoncreds_proof_request must be populated"
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
    anoncreds_presentation_spec: Optional[AnonCredsPresSpec] = None
    dif_presentation_spec: Optional[DIFPresSpec] = None

    @model_validator(mode="after")
    def validate_specs(self) -> "AcceptProofRequest":
        if (
            self.anoncreds_presentation_spec is None
            and self.dif_presentation_spec is None
        ):
            raise CloudApiValueError(
                "One of anoncreds_presentation_spec or dif_presentation_spec should be provided"
            )

        if (
            self.anoncreds_presentation_spec is not None
            and self.dif_presentation_spec is not None
        ):
            raise CloudApiValueError(
                "Only one of anoncreds_presentation_spec or dif_presentation_spec should be provided"
            )

        return self


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
