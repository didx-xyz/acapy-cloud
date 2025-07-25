import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from shared.exceptions import CloudApiValueError
from shared.models.trustregistry import TrustRegistryRole

# Deduplicate some descriptions and field definitions
allowable_special_chars = ".!@$*()~_-"  # the dash character must be at the end, otherwise it defines a regex range
label_description = (
    "A required alias for the tenant, publicized to other agents when forming a connection. "
    "If the tenant is an issuer or verifier, this label will be displayed on the trust registry and must be unique. "
    f"Allowable special characters: {allowable_special_chars}"
)
label_examples = ["Tenant Label"]
group_id_field = Field(
    None,
    description="An optional group identifier. Useful with `get_tenants` to fetch wallets by group id.",
    examples=["Some-Group-Id"],
)
image_url_field = Field(
    None,
    examples=["https://upload.wikimedia.org/wikipedia/commons/7/70/Example.png"],
)
ExtraSettings = Literal[
    "ACAPY_INVITE_PUBLIC",
    "ACAPY_PUBLIC_INVITES",
    "ACAPY_AUTO_ACCEPT_INVITES",
    "ACAPY_AUTO_ACCEPT_REQUESTS",
    "ACAPY_AUTO_PING_CONNECTION",
    "ACAPY_AUTO_RESPOND_MESSAGES",
    "ACAPY_AUTO_RESPOND_CREDENTIAL_OFFER",
    "ACAPY_AUTO_RESPOND_CREDENTIAL_REQUEST",
    "ACAPY_AUTO_VERIFY_PRESENTATION",
    # "ACAPY_LOG_LEVEL",
    # "ACAPY_MONITOR_PING",
    # "ACAPY_NOTIFY_REVOCATION",
    # "ACAPY_AUTO_REQUEST_ENDORSEMENT",
    # "ACAPY_AUTO_WRITE_TRANSACTIONS",
    # "ACAPY_CREATE_REVOCATION_TRANSACTIONS",
    # "ACAPY_ENDORSER_ROLE",
]
ExtraSettings_field = Field(
    None,
    description=(
        "Optional, advanced settings to configure wallet behaviour. If you don't know what these are, "
        "then you probably don't need them."
    ),
)


class CreateTenantRequest(BaseModel):
    wallet_label: str = Field(
        ..., description=label_description, examples=label_examples
    )
    wallet_name: str | None = Field(
        None,
        description="An optional wallet name. Useful with `get_tenants` to fetch wallets by wallet name. "
        "If selected, must be unique. Otherwise, randomly generated.",
        examples=["Unique name"],
    )
    roles: list[TrustRegistryRole] | None = None
    group_id: str | None = group_id_field
    image_url: str | None = image_url_field
    extra_settings: dict[ExtraSettings, bool] | None = ExtraSettings_field

    @field_validator("wallet_label", mode="before")
    @classmethod
    def validate_wallet_label(cls, v: str) -> str:
        if len(v) > 100:
            raise CloudApiValueError("wallet_label has a max length of 100 characters")

        if not re.match(rf"^[a-zA-Z0-9 {allowable_special_chars}]+$", v):
            raise CloudApiValueError(
                "wallet_label may not contain certain special characters. Must be alphanumeric, may include "
                f"spaces, and the following special characters are allowed: {allowable_special_chars}"
            )
        return v

    @field_validator("wallet_name", mode="before")
    @classmethod
    def validate_wallet_name(cls, v: str | None) -> str | None:
        if v:
            if len(v) > 100:
                raise CloudApiValueError(
                    "wallet_name has a max length of 100 characters"
                )

            if not re.match(rf"^[a-zA-Z0-9 {allowable_special_chars}]+$", v):
                raise CloudApiValueError(
                    "wallet_name may not contain certain special characters. Must be alphanumeric, may include "
                    f"spaces, and the following special characters are allowed: {allowable_special_chars}"
                )

        return v

    @field_validator("group_id", mode="before")
    @classmethod
    def validate_group_id(cls, v: str | None) -> str | None:
        if v:
            if len(v) > 50:
                raise CloudApiValueError("group_id has a max length of 50 characters")

            if not re.match(rf"^[a-zA-Z0-9{allowable_special_chars}]+$", v):
                raise CloudApiValueError(
                    "group_id may not contain spaces, or certain special characters. Must be alphanumeric "
                    f"and the following special characters are allowed: {allowable_special_chars}"
                )

        return v


class UpdateTenantRequest(BaseModel):
    wallet_label: str | None = Field(
        None, description=label_description, examples=label_examples
    )
    roles: list[TrustRegistryRole] | None = None
    image_url: str | None = image_url_field
    extra_settings: dict[ExtraSettings, bool] | None = ExtraSettings_field

    @field_validator("wallet_label", mode="before")
    @classmethod
    def validate_wallet_label(cls, v: str) -> str:
        if len(v) > 100:
            raise CloudApiValueError("wallet_label has a max length of 100 characters")

        if not re.match(rf"^[a-zA-Z0-9 {allowable_special_chars}]+$", v):
            raise CloudApiValueError(
                "wallet_label may not contain certain special characters. Must be alphanumeric, may include "
                f"spaces, and the following special characters are allowed: {allowable_special_chars}"
            )
        return v


class Tenant(BaseModel):
    wallet_id: str = Field(..., examples=["545135a4-ecbc-4400-8594-bdb74c51c88d"])
    wallet_label: str = Field(..., examples=["Alice"])
    wallet_name: str = Field(..., examples=["SomeWalletName"])
    created_at: str = Field(...)
    updated_at: str | None = Field(None)
    image_url: str | None = image_url_field
    group_id: str | None = group_id_field


class TenantAuth(BaseModel):
    access_token: str = Field(..., examples=["ey..."])


class CreateTenantResponse(Tenant, TenantAuth):
    pass


class OnboardResult(BaseModel):
    did: str
    didcomm_invitation: str | None = None
