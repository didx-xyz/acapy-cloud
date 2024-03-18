from typing import Dict, Optional

from pydantic import BaseModel, Field, model_validator

from shared.exceptions import CloudApiValueError


class JWSCreateRequest(BaseModel):
    did: Optional[str] = Field(
        None, examples=["did:key:z6MkjCjxuTXxVPWS9JYj2ZiKtKvSS1srC6kBRes4WCB2mSWq"]
    )
    headers: Dict = Field(default={})
    payload: Dict = Field(default={})
    verification_method: Optional[str] = Field(
        None,
        description="Information used for proof verification",
        examples=[
            "did:key:z6MkjCjxuTXxVPWS9JYj2ZiKtKvSS1srC6kBRes4WCB2mSWq#z6MkjCj"
            "xuTXxVPWS9JYj2ZiKtKvSS1srC6kBRes4WCB2mSWq"
        ],
    )

    @model_validator(mode="before")
    @classmethod
    def check_at_least_one_field_is_populated(cls, values):
        did, verification_method = values.get("did"), values.get("verification_method")
        if not did and not verification_method:
            raise CloudApiValueError(
                "At least one of `did` or `verification_method` must be populated."
            )
        return values


class JWSCreateResponse(BaseModel):
    jws: str = Field(
        ...,
        examples=[
            "eyJ0eXAiOiAiSldUIiwgImFsZyI6ICJFZERTQSIsICJraWQiOiAiZGlkOmtleTp6Nk1rakNqeHVUWHhWUFdTOUpZajJaaUt0S3ZTUzFz"
            "ckM2a0JSZXM0V0NCMm1TV3EjejZNa2pDanh1VFh4VlBXUzlKWWoyWmlLdEt2U1Mxc3JDNmtCUmVzNFdDQjJtU1dxIn0.e30.rOLhhAaM"
            "fWb_rFzgKofXRuv72bj7SjRcPieICMV1TE1eJrTG-RoIJ6crrEc_mRmnFtI7dExEZAnCqd4LzGozAA"
        ],
    )


class JWSVerifyRequest(JWSCreateResponse):
    pass  # Verify request is same as create response


class JWSVerifyResponse(BaseModel):
    error: Optional[str] = Field(default=None, description="Error text")
    headers: Dict = Field(
        description="Headers from verified JWT.",
        examples=[
            {
                "typ": "JWT",
                "alg": "EdDSA",
                "kid": "did:key:z6MkjCjxuTXxVPWS9JYj2ZiKtKvSS1srC6kBRes4WCB2mSWq#z6MkjCjxuTXxVPWS9JYj2ZiKtKvSS1srC6kB"
                "Res4WCB2mSWq",
            }
        ],
    )
    kid: str = Field(
        description="kid of signer",
        examples=[
            "did:key:z6MkjCjxuTXxVPWS9JYj2ZiKtKvSS1srC6kBRes4WCB2mSWq#z6MkjCjxuTXxVPWS9JYj2ZiKtKvSS1srC6kBRes4WCB2mSWq"
        ],
    )
    payload: Dict = Field(description="Payload from verified JWT")
    valid: bool = Field(...)
