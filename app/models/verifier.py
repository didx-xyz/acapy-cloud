from enum import Enum
from typing import Any, Literal, Union

from aries_cloudcontroller import (
    AnonCredsPresentationRequest as AcaPyAnonCredsPresentationRequest,
)
from aries_cloudcontroller import (
    AnonCredsPresSpec,
    DIFPresSpec,
    DIFProofRequest,
    IndyNonRevocationInterval,
)
from pydantic import BaseModel, Field, field_validator, model_validator

from app.util.save_exchange_record import SaveExchangeRecordField
from shared.exceptions import CloudApiValueError


class RevocationStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    NOT_CHECKED = "not-checked"
    CHECK_FAILED = "check-failed"


class AnonCredsPresentationRequest(AcaPyAnonCredsPresentationRequest):
    name: str = Field(default="Proof", description="Proof request name")
    version: str = Field(default="1.0", description="Proof request version")


class ProofRequestBase(BaseModel):
    anoncreds_proof_request: AnonCredsPresentationRequest | None = None
    dif_proof_request: DIFProofRequest | None = None

    @model_validator(mode="before")
    @classmethod
    def check_proof_request(cls, values: Union[dict, "ProofRequestBase"]) -> dict:
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
                "Only one of anoncreds_proof_request or dif_proof_request must be populated"
            )

        return values

    def get_proof_type(self) -> Literal["anoncreds", "dif"]:
        if self.anoncreds_proof_request is not None:
            return "anoncreds"
        elif self.dif_proof_request is not None:
            return "dif"
        else:
            raise CloudApiValueError("No proof type provided")


class ProofRequestMetadata(BaseModel):
    comment: str | None = None


class CreateProofRequest(
    ProofRequestBase, ProofRequestMetadata, SaveExchangeRecordField
):
    pass


class SendProofRequest(CreateProofRequest):
    connection_id: str


class ProofId(BaseModel):
    proof_id: str


class AcceptProofRequest(ProofId, SaveExchangeRecordField):
    anoncreds_presentation_spec: AnonCredsPresSpec | None = None
    dif_presentation_spec: DIFPresSpec | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_specs(cls, values: Union[dict, "ProofRequestBase"]) -> dict:
        # pydantic v2 removed safe way to get key, because `values` can be a dict or this type
        if not isinstance(values, dict):
            values = values.__dict__

        dif_pres_spec = values.get("dif_presentation_spec")
        anoncreds_pres_spec = values.get("anoncreds_presentation_spec")

        if anoncreds_pres_spec is None and dif_pres_spec is None:
            raise CloudApiValueError(
                "One of anoncreds_presentation_spec or dif_presentation_spec must be populated"
            )

        if anoncreds_pres_spec is not None and dif_pres_spec is not None:
            raise CloudApiValueError(
                "Only one of anoncreds_presentation_spec or dif_presentation_spec must be populated"
            )

        return values

    def get_proof_type(self) -> Literal["anoncreds", "dif"]:
        if self.anoncreds_presentation_spec is not None:
            return "anoncreds"
        elif self.dif_presentation_spec is not None:
            return "dif"
        else:
            raise CloudApiValueError("No proof type provided")


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
    def validate_problem_report(cls, value: str) -> str:
        if value == "":
            raise CloudApiValueError("problem_report cannot be an empty string")
        return value


class CredInfo(BaseModel):
    attrs: dict[str, Any] | None = Field(
        default=None, description="Attribute names and value"
    )
    cred_def_id: str | None = Field(
        default=None, description="Credential definition identifier"
    )
    referent: str | None = Field(
        default=None, description="removed - renamed to credential_id", exclude=True
    )
    credential_id: str | None = Field(
        default=None, description="Credential identifier", validation_alias="referent"
    )
    cred_rev_id: str | None = Field(
        default=None, description="Credential revocation identifier"
    )
    rev_reg_id: str | None = Field(
        default=None, description="Revocation registry identifier"
    )
    schema_id: str | None = Field(default=None, description="Schema identifier")
    revocation_status: RevocationStatus | None = Field(
        default=None, description="Revocation status of the credential"
    )

    @model_validator(mode="after")
    def validate_revocation_status(self) -> "CredInfo":
        if self.rev_reg_id is None:
            self.revocation_status = None
        elif self.rev_reg_id is not None and self.revocation_status is None:
            self.revocation_status = RevocationStatus.NOT_CHECKED

        return self


class NonRevocationInterval(IndyNonRevocationInterval):
    # We just rename the model to avoid confusion with AnonCreds using this
    pass


class CredPrecis(BaseModel):
    cred_info: CredInfo = Field(description="Credential info")
    interval: NonRevocationInterval | None = Field(
        default=None, description="Non-revocation interval from presentation request"
    )
    presentation_referents: list[str] | None = Field(
        default=None, description="Presentation referents"
    )
