from enum import Enum
from typing import Any, Dict, List, Optional

from aries_cloudcontroller import LDProofVCDetail, TxnOrPublishRevocationsResult
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from app.util.save_exchange_record import SaveExchangeRecordField
from shared.exceptions import CloudApiValueError


class CredentialType(str, Enum):
    INDY: str = "indy"
    JWT: str = "jwt"
    LD_PROOF: str = "ld_proof"
    ANONCREDS: str = "anoncreds"


class IndyCredential(BaseModel):
    credential_definition_id: str
    attributes: Dict[str, str]


class AnonCredsCredential(BaseModel):
    credential_definition_id: str
    issuer_did: Optional[str] = Field(
        default=None,
        description=(
            "The DID to use as the issuer of the credential. "
            "If not provided, the public DID of the issuer wallet will be used."
        ),
    )
    attributes: Dict[str, str]


class CredentialBase(SaveExchangeRecordField):
    type: CredentialType = CredentialType.INDY
    indy_credential_detail: Optional[IndyCredential] = None
    ld_credential_detail: Optional[LDProofVCDetail] = None
    anoncreds_credential_detail: Optional[AnonCredsCredential] = None

    @field_validator("indy_credential_detail", mode="before")
    @classmethod
    def check_indy_credential_detail(cls, value, values: ValidationInfo):
        if values.data.get("type") == CredentialType.INDY and value is None:
            raise CloudApiValueError(
                "indy_credential_detail must be populated if `indy` credential type is selected"
            )
        return value

    @field_validator("ld_credential_detail", mode="before")
    @classmethod
    def check_ld_credential_detail(cls, value, values: ValidationInfo):
        if values.data.get("type") == CredentialType.LD_PROOF and value is None:
            raise CloudApiValueError(
                "ld_credential_detail must be populated if `ld_proof` credential type is selected"
            )
        return value

    @field_validator("anoncreds_credential_detail", mode="before")
    @classmethod
    def check_anoncreds_credential_detail(cls, value, values: ValidationInfo):
        if values.data.get("type") == CredentialType.ANONCREDS and value is None:
            raise CloudApiValueError(
                "anoncreds_credential_detail must be populated if `anoncreds` credential type is selected"
            )
        return value


class CredentialWithConnection(CredentialBase):
    connection_id: str


class SendCredential(CredentialWithConnection):
    pass


class CreateOffer(CredentialBase):
    pass


class RevokeCredential(BaseModel):
    credential_exchange_id: str
    auto_publish_on_ledger: bool = False


class PublishRevocationsRequest(BaseModel):
    revocation_registry_credential_map: Dict[str, List[str]] = Field(
        default={},
        description=(
            "A map of revocation registry IDs to lists of credential revocation IDs that should be published. "
            "Providing an empty list for a registry ID publishes all pending revocations for that ID. "
            "An empty dictionary signifies that the action should be applied to all pending revocations across "
            "all registry IDs."
        ),
    )


class ClearPendingRevocationsRequest(BaseModel):
    revocation_registry_credential_map: Dict[str, List[str]] = Field(
        default={},
        description=(
            "A map of revocation registry IDs to lists of credential revocation IDs for which pending revocations "
            "should be cleared. Providing an empty list for a registry ID clears all pending revocations for that ID. "
            "An empty dictionary signifies that the action should be applied to clear all pending revocations across "
            "all registry IDs."
        ),
    )


class ClearPendingRevocationsResult(BaseModel):
    revocation_registry_credential_map: Dict[str, List[str]] = Field(
        description=(
            "The resulting revocations that are still pending after a clear-pending request has been completed."
        ),
    )


class RevokedResponse(BaseModel):
    cred_rev_ids_published: Dict[str, List[int]] = Field(
        default_factory=dict,
        description=(
            "A map of revocation registry IDs to lists of credential revocation IDs "
            "(as integers) that have been revoked."
            "When cred_rev_ids_published is empty no revocations were published."
            "This will happen when revoke is called with auto_publish_on_ledger=False."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def extract_revoked_info(
        cls, values: TxnOrPublishRevocationsResult
    ) -> Dict[str, Any]:
        if isinstance(values, dict) and "txn" in values:
            # This is a List of TransactionRecord
            txn_list: List[Dict[str, Any]] = values.get("txn")
            cred_rev_ids_published = {}

            for txn in txn_list:
                for attach in txn.get("messages_attach", []):
                    data = attach.get("data", {}).get("json", {})
                    operation = data.get("operation", {})
                    revoc_reg_def_id = operation.get("revocRegDefId")
                    revoked = operation.get("value", {}).get("revoked", [])
                    if revoc_reg_def_id and revoked:
                        cred_rev_ids_published[revoc_reg_def_id] = revoked

            values["cred_rev_ids_published"] = cred_rev_ids_published

        return values


class PendingRevocations(BaseModel):
    pending_cred_rev_ids: list[Optional[int]] = []
