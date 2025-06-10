from pydantic import BaseModel, Field

from app.models.jws import JWSCreateRequest, JWSVerifyResponse


class SDJWSCreateRequest(JWSCreateRequest):  # extend JWSCreateRequest model
    non_sd_list: list[str] | None = Field(
        default=[],
        examples=[
            [
                "name",
                "address",
                "address.street_address",
                "nationalities[1:3]",
            ]
        ],
    )


class SDJWSCreateResponse(BaseModel):
    sd_jws: str = Field(
        ...,
        examples=[
            (
                "eyJhbGciOiJFZERTQSJ9."
                "eyJhIjogIjAifQ."
                "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
                "~WyJEM3BUSFdCYWNRcFdpREc2TWZKLUZnIiwgIkRFIl0"
                "~WyJPMTFySVRjRTdHcXExYW9oRkd0aDh3IiwgIlNBIl0"
                "~WyJkVmEzX1JlTGNsWTU0R1FHZm5oWlRnIiwgInVwZGF0ZWRfYXQiLCAxNTcwMDAwMDAwXQ"
            )
        ],
    )


class SDJWSVerifyRequest(SDJWSCreateResponse):
    pass  # Verify request is same as create response


class SDJWSVerifyResponse(JWSVerifyResponse):  # extend JWSVerifyResponse model
    disclosures: list[list[str | dict]] = Field(
        ...,
        description="Disclosure arrays associated with the SD-JWT",
        examples=[
            [
                ["fx1iT_mETjGiC-JzRARnVg", "name", "Alice"],
                [
                    "n4-t3mlh8jSS6yMIT7QHnA",
                    "street_address",
                    {"_sd": ["kLZrLK7enwfqeOzJ9-Ss88YS3mhjOAEk9lr_ix2Heng"]},
                ],
            ]
        ],
    )
