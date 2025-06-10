from typing import Any, Literal

from aries_cloudcontroller import LDProofVCDetail, TxnOrPublishRevocationsResult
from pydantic import BaseModel, Field, model_validator

from app.util.save_exchange_record import SaveExchangeRecordField
from shared.exceptions import CloudApiValueError


class AnonCredsCredential(BaseModel):
    credential_definition_id: str
    issuer_did: str | None = Field(
        default=None,
        description=(
            "The DID to use as the issuer of the credential. "
            "If not provided, the public DID of the issuer wallet will be used."
        ),
    )
    attributes: dict[str, str]


class CredentialBase(SaveExchangeRecordField):
    ld_credential_detail: LDProofVCDetail | None = None
    anoncreds_credential_detail: AnonCredsCredential | None = None

    @model_validator(mode="after")
    def check_credential_detail(self):
        if (
            self.anoncreds_credential_detail is None
            and self.ld_credential_detail is None
        ):
            raise CloudApiValueError(
                "One of anoncreds_credential_detail or ld_credential_detail must be populated"
            )

        if (
            self.anoncreds_credential_detail is not None
            and self.ld_credential_detail is not None
        ):
            raise CloudApiValueError(
                "Only one of anoncreds_credential_detail or ld_credential_detail must be populated"
            )

        return self

    def get_credential_type(self) -> Literal["anoncreds", "ld_proof"]:
        if self.anoncreds_credential_detail is not None:
            return "anoncreds"
        elif self.ld_credential_detail is not None:
            return "ld_proof"
        else:
            raise CloudApiValueError("No credential detail provided")


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
    revocation_registry_credential_map: dict[str, list[str]] = Field(
        default={},
        description=(
            "A map of revocation registry IDs to lists of credential revocation IDs that should be published. "
            "Providing an empty list for a registry ID publishes all pending revocations for that ID. "
            "An empty dictionary signifies that the action should be applied to all pending revocations across "
            "all registry IDs."
        ),
    )


class ClearPendingRevocationsRequest(BaseModel):
    revocation_registry_credential_map: dict[str, list[str]] = Field(
        default={},
        description=(
            "A map of revocation registry IDs to lists of credential revocation IDs for which pending revocations "
            "should be cleared. Providing an empty list for a registry ID clears all pending revocations for that ID. "
            "An empty dictionary signifies that the action should be applied to clear all pending revocations across "
            "all registry IDs."
        ),
    )


class ClearPendingRevocationsResult(BaseModel):
    revocation_registry_credential_map: dict[str, list[str]] = Field(
        description=(
            "The resulting revocations that are still pending after a clear-pending request has been completed."
        ),
    )


class RevokedResponse(BaseModel):
    cred_rev_ids_published: dict[str, list[int]] = Field(
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
    ) -> dict[str, Any]:
        if isinstance(values, dict) and "txn" in values:
            # This is a List of TransactionRecord
            txn_list: list[dict[str, Any]] = values.get("txn") or []
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
    pending_cred_rev_ids: list[int | None] = []
