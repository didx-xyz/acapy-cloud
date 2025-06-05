from typing import Literal, Optional

from aries_cloudcontroller import DID, AcaPyClient
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.exceptions.cloudapi_exception import CloudApiException
from app.services import acapy_wallet
from app.services.acapy_ledger import accept_taa_if_required
from shared.constants import LEDGER_REGISTRATION_URL, LEDGER_TYPE
from shared.log_config import get_logger
from shared.util.rich_async_client import RichAsyncClient

logger = get_logger(__name__)


class LedgerRequestSovrin(BaseModel):
    network: Optional[str] = Field(None)
    did: Optional[str] = Field(None)
    verkey: Optional[str] = Field(None)
    payment_address: Optional[str] = Field(None, alias="paymentaddr")


class LedgerRequestVon(BaseModel):
    did: Optional[str] = Field(None)
    seed: Optional[str] = Field(None)
    verkey: Optional[str] = Field(None)
    role: Optional[str] = Field(None)


async def post_to_ledger(
    did: str, verkey: str, role: Optional[Literal["ENDORSER"]] = "ENDORSER"
) -> None:
    if LEDGER_TYPE == "sovrin":
        payload = LedgerRequestSovrin(
            network="stagingnet",
            did=did,
            verkey=verkey,
        )
    elif LEDGER_TYPE == "von":
        payload = LedgerRequestVon(did=did, verkey=verkey, role=role)
    else:
        raise HTTPException(
            status_code=501,
            detail="Cannot resolve ledger type. Should be either von or sovrin",
        )

    logger.debug("Try post to ledger: {}", payload)
    async with RichAsyncClient(raise_status_error=False) as client:
        response = await client.post(
            LEDGER_REGISTRATION_URL, json=payload.model_dump(), timeout=300
        )

    if response.is_error:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Something went wrong.\nCould not write to Ledger.\n{response.text}",
        )
    logger.info("Successfully posted to ledger.")


async def has_public_did(aries_controller: AcaPyClient) -> bool:
    try:
        await acapy_wallet.get_public_did(aries_controller)
        return True
    except CloudApiException:
        return False


async def create_public_did(
    aries_controller: AcaPyClient, set_public: bool = True
) -> DID:
    logger.info("Handling create public did request")
    did_object = await acapy_wallet.create_did(aries_controller)

    if not did_object.did or not did_object.verkey:
        raise CloudApiException("Cannot register did without did and/or verkey")

    if not did_object.did.startswith("did:cheqd:"):
        await post_to_ledger(did=did_object.did, verkey=did_object.verkey)
        await accept_taa_if_required(aries_controller)

        if set_public:
            await acapy_wallet.set_public_did(aries_controller, did_object.did)

    logger.debug("Successfully handled create public did request.")
    return did_object
