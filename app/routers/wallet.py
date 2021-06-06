from fastapi import APIRouter, HTTPException, Header
import os
import logging
from typing import Optional
import traceback

from schemas import LedgerRequest, DidCreationResponse, InitWalletRequest
from utils import (
    create_controller,
    create_did,
    post_to_ledger,
    get_taa,
    accept_taa,
    assign_pub_did,
    get_pub_did,
    get_did_endpoint,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallets", tags=["wallets"])

admin_url = os.getenv("ACAPY_ADMIN_URL")
admin_port = os.getenv("ACAPY_ADMIN_PORT")
# TODO Should the admin_api_key be a dummy variable so the controller doesn't function w/o providing it?
# This all smells really - this has to be done in a better manner
admin_api_key = os.getenv("ACAPY_ADMIN_API_KEY")
is_multitenant = os.getenv("IS_MULTITENANT", False)
ledger_url = os.getenv("LEDGER_NETWORK_URL")


@router.get("/create-pub-did", tags=["did"], response_model=DidCreationResponse)
async def create_public_did(req_header: Optional[str] = Header(None)):
    """
    Create a new public DID and
    write it to the ledger and
    receive its public info.

    Returns:
    * DID object (json)
    * Issuer verkey (str)
    * Issuer Endpoint (url)
    """
    try:
        async with create_controller(req_header) as controller:
            # TODO: Should this come from env var or from the client request?
            if "ledger_url" in req_header:
                url = req_header["ledger_url"]
            else:
                url = ledger_url
            # Adding empty header as parameters are being sent in payload
            generate_did_res = await create_did(controller)
            did_object = generate_did_res["result"]
            # TODO: Network and paymentaddr should be definable on the fly/via args/via request body
            # TODO: Should this really be a schema or is using schema overkill here?
            # If we leave it as schema like this I suppose it is at least usable elsewhere
            payload = LedgerRequest(
                network="stagingnet",
                did=did_object["did"],
                verkey=did_object["verkey"],
                paymentaddr="",
            ).dict()

            await post_to_ledger(url, payload)

            TAA = await get_taa(controller)

            await accept_taa(controller, TAA)

            await assign_pub_did(controller, did_object)

            get_pub_did_response = await get_pub_did(controller)
            issuer_nym = get_pub_did_response["result"]["did"]
            issuer_verkey = get_pub_did_response["result"]["verkey"]
            issuer_endpoint = await get_did_endpoint(controller, issuer_nym)
            issuer_endpoint_url = issuer_endpoint["endpoint"]
            final_response = DidCreationResponse(
                did_object=did_object,
                issuer_verkey=issuer_verkey,
                issuer_endpoint=issuer_endpoint_url,
            )
            return final_response
    except Exception as e:
        err_trace = traceback.print_exc()
        logger.error(f"The following error occured:\n{e!r}\n{err_trace}")
        raise e


@router.get("/")
async def wallets_root():
    """
    The default endpoints for wallets

    TODO: Determine what this should return or
    whether this should return anything at all
    """
    return {
        "message": "Wallets endpoint. Please, visit /docs to consult the Swagger docs."
    }


# TODO: This should be somehow retsricted?!
@router.post("/create-wallet")
async def create_wallet(
    wallet_payload: InitWalletRequest, req_header: Optional[str] = Header(None)
):
    """
    Create a new wallet

    Parameters:
    -----------
    wallet_payload: dict
    """
    try:
        async with create_controller(req_header) as controller:
            if controller.is_multitenant:
                # TODO replace with model for payload/wallet like
                # described https://fastapi.tiangolo.com/tutorial/body/
                # TODO Remove this default wallet. This has to be provided
                # At least unique values for eg label, The rest could be filled
                # with default values like image_url could point to a defautl avatar img
                if not wallet_payload:
                    payload = {
                        "image_url": "https://aries.ca/images/sample.png",
                        "key_management_mode": "managed",
                        "label": "Alice",
                        "wallet_dispatch_type": "default",
                        "wallet_key": "MySecretKey1234",
                        "wallet_name": "AlicesWallet",
                        "wallet_type": "indy",
                    }
                else:
                    payload = wallet_payload
                wallet_response = await controller.multitenant.create_subwallet(payload)
            else:
                # TODO: Implement wallet_response as schema if that is useful
                wallet_response = await controller.wallet.create_did()
            return wallet_response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Something went wrong: {e!r}",
        )
