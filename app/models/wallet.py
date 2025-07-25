from typing import Literal

from aries_cloudcontroller.models.did_create import DIDCreate as DIDCreateAcaPy
from aries_cloudcontroller.models.did_create_options import DIDCreateOptions
from aries_cloudcontroller.models.vc_record import VCRecord as VCRecordAcaPy
from pydantic import BaseModel, Field, StrictStr

from app.models.verifier import CredInfo


class SetDidEndpointRequest(BaseModel):
    endpoint: str = Field(...)


class VCRecord(VCRecordAcaPy):
    credential_id: str = Field(
        ..., validation_alias="record_id", description="Credential identifier"
    )
    record_id: str = Field(
        ...,
        description="removed - renamed to credential_id",
        exclude=True,
    )


class VCRecordList(BaseModel):
    results: list[VCRecord] | None = None


class CredInfoList(BaseModel):
    results: list[CredInfo] | None = None


class DIDCreate(BaseModel):
    # Extends the AcapyDIDCreate model with smart defaults and a simplified interface.
    # Downstream processes should use the `to_acapy_options` method to convert the model's fields
    # into the `DIDCreateOptions` structure expected by ACA-Py.

    _supported_methods = ["cheqd", "key", "web", "did:peer:2", "did:peer:4"]

    method: StrictStr = Field(
        default="cheqd",
        description=(
            "Method for the requested DID. Supported methods are "
            f"{', '.join(_supported_methods)}."
        ),
        examples=_supported_methods,
    )
    seed: StrictStr | None = Field(
        default=None,
        description="Optional seed to use for DID. Must be enabled in configuration before use.",
    )
    key_type: StrictStr = Field(
        default="ed25519",
        description="Key type to use for the DID key_pair. Validated with the chosen DID method's supported key types.",
        examples=["ed25519", "bls12381g2"],
    )
    did: StrictStr | None = Field(
        default=None,
        description="Specify the final value of DID (including `did:<method>:` prefix) if the method supports it.",
    )
    network: Literal["mainnet", "testnet"] | None = Field(
        default=None,
        description="Specify the network to use for Cheqd DIDs. Valid values are `mainnet` and `testnet`.",
        examples=["mainnet", "testnet"],
    )

    def to_acapy_options(self) -> DIDCreateOptions:
        """Convert the model's fields into the `DIDCreateOptions` structure expected by ACA-Py.

        Returns:
            An instance of `DIDCreateOptions` populated with `key_type` and `did`.

        """
        return DIDCreateOptions(key_type=self.key_type, did=self.did)

    def to_acapy_request(self) -> DIDCreateAcaPy:
        return DIDCreateAcaPy(
            method=self.method,
            options=self.to_acapy_options(),
        )
