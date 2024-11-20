from secrets import token_urlsafe
from typing import List, Optional
from uuid import uuid4

import base58
from aries_cloudcontroller import CreateWalletTokenRequest
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.acapy_clients import get_tenant_admin_controller
from app.dependencies.auth import (
    AcaPyAuthVerified,
    acapy_auth_tenant_admin,
    tenant_api_key,
)
from app.exceptions import (
    CloudApiException,
    TrustRegistryException,
    handle_acapy_call,
    handle_model_with_validation,
)
from app.models.tenants import (
    CreateTenantRequest,
    CreateTenantResponse,
    CreateWalletRequestWithGroups,
    Tenant,
    TenantAuth,
    UpdateTenantRequest,
)
from app.services.onboarding.tenants import handle_tenant_update, onboard_tenant
from app.services.trust_registry.actors import (
    fetch_actor_by_id,
    register_actor,
    remove_actor_by_id,
)
from app.services.trust_registry.util.actor import assert_actor_name
from app.util.pagination import (
    descending_query_parameter,
    limit_query_parameter,
    offset_query_parameter,
    order_by_query_parameter,
)
from app.util.tenants import (
    get_wallet_and_assert_valid_group,
    tenant_from_wallet_record,
)
from shared.log_config import get_logger
from shared.models.trustregistry import Actor

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/tenants", tags=["admin: tenants"])


group_id_query: Optional[str] = Query(
    default=None,
    description="Group ID to which the wallet belongs",
    include_in_schema=False,
)


@router.post("", response_model=CreateTenantResponse, summary="Create a new Tenant")
async def create_tenant(
    body: CreateTenantRequest,
    admin_auth: AcaPyAuthVerified = Depends(acapy_auth_tenant_admin),
) -> CreateTenantResponse:
    """
    Create a new Tenant
    ---

    Use this endpoint to create a Tenant, which generates a Wallet and onboards it with the specified roles.

    The `wallet_name` is an optional field that allows you to assign a name to the wallet,
    useful with `get_tenants` to fetch Wallets by Wallet name.

    The roles can be `issuer` or `verifier`. If no roles are provided, the Tenant will be created
    without any roles and be considered a `holder`.

    The `image_url` is an optional field that allows you to assign an image to the Wallet.

    Tenants onboarded with roles will be added to the trust registry.

    `extra_settings` is an optional field that allows you to configure the wallet behaviour for advanced users.

    Request body:
    ---
        body: CreateTenantRequest
            wallet_label: str
                A required alias for the Tenant.
            wallet_name: Optional[str]
                An optional wallet name.
            roles: Optional[List[str]]
                A list of roles to assign to the Tenant.
            image_url: Optional[str]
                An optional image URL for the Tenant.
            extra_settings: Optional[Dict[str, Union[bool, str]]]
                Optional per-tenant settings to configure wallet behaviour for advanced users.

    Response body:
    ---
        CreateTenantResponse
            wallet_id: str
            wallet_label: str
            wallet_name: str
            created_at: str
            image_url: Optional[str]
            group_id: Optional[str]
            updated_at: str
            access_token: str
    """
    bound_logger = logger.bind(body=body)
    bound_logger.debug("POST request received: Starting tenant creation")

    roles = body.roles
    wallet_label = body.wallet_label
    wallet_name = body.wallet_name or uuid4().hex

    bound_logger.debug("Assert that requested label is not used in trust registry")
    try:
        actor_name_exists = await assert_actor_name(wallet_label)
    except TrustRegistryException as e:
        raise CloudApiException(
            "An error occurred when trying to register actor. Please try again"
        ) from e

    if actor_name_exists:
        bound_logger.info("Actor name already exists; can't create wallet")
        raise HTTPException(
            409,
            f"Can't create Tenant. The label `{wallet_label}` may not "
            "be re-used because it exists on the trust registry.",
        )
    bound_logger.debug("Actor name is unique")

    wallet_response = None
    body_request = handle_model_with_validation(
        logger=bound_logger,
        model_class=CreateWalletRequestWithGroups,
        image_url=body.image_url,
        key_management_mode="managed",
        label=wallet_label,
        wallet_key=base58.b58encode(token_urlsafe(48)).decode(),
        wallet_name=wallet_name,
        wallet_type="askar",
        group_id=body.group_id,
        extra_settings=body.extra_settings,
    )
    async with get_tenant_admin_controller(admin_auth) as admin_controller:
        try:
            bound_logger.debug("Creating wallet")
            wallet_response = await handle_acapy_call(
                logger=bound_logger,
                acapy_call=admin_controller.multitenancy.create_wallet,
                body=body_request,
            )
        except CloudApiException as e:
            bound_logger.info(
                "Error while trying to create wallet: `{}`",
                e.detail,
            )
            if e.status_code == 400 and "already exists" in e.detail:
                raise HTTPException(
                    409,
                    f"A wallet with name `{wallet_name}` already exists. "
                    "The wallet name must be unique.",
                ) from e
            raise

        bound_logger.debug("Wallet creation successful")

        try:
            if roles:
                bound_logger.debug(
                    "Onboarding `{}` with requested roles: `{}`", wallet_label, roles
                )
                onboard_result = await onboard_tenant(
                    tenant_label=wallet_label,
                    roles=roles,
                    wallet_auth_token=wallet_response.token,
                    wallet_id=wallet_response.wallet_id,
                )
                bound_logger.debug("Registering actor in the trust registry")
                await register_actor(
                    actor=Actor(
                        id=wallet_response.wallet_id,
                        name=wallet_label,
                        roles=roles,
                        did=onboard_result.did,
                        didcomm_invitation=onboard_result.didcomm_invitation,
                        image_url=body.image_url,
                    )
                )
        except HTTPException as http_error:
            bound_logger.error("Could not register actor: {}", http_error.detail)
            if wallet_response:
                bound_logger.info(
                    "Stray wallet was created for unregistered actor; deleting wallet"
                )
                await handle_acapy_call(
                    logger=bound_logger,
                    acapy_call=admin_controller.multitenancy.delete_wallet,
                    wallet_id=wallet_response.wallet_id,
                )
                bound_logger.info("Wallet deleted.")
            raise
        except Exception:
            bound_logger.exception("An unhandled exception occurred")
            if wallet_response:
                bound_logger.info(
                    "Could not register actor, but wallet was created; deleting wallet"
                )
                await handle_acapy_call(
                    logger=bound_logger,
                    acapy_call=admin_controller.multitenancy.delete_wallet,
                    wallet_id=wallet_response.wallet_id,
                )
                bound_logger.info("Wallet deleted.")
            raise

    response = CreateTenantResponse(
        wallet_id=wallet_response.wallet_id,
        wallet_label=wallet_label,
        wallet_name=wallet_name,
        created_at=wallet_response.created_at,
        image_url=body.image_url,
        updated_at=wallet_response.updated_at,
        access_token=tenant_api_key(wallet_response.token),
        group_id=body.group_id,
    )
    bound_logger.debug("Successfully created tenant.")
    return response


@router.delete("/{wallet_id}", summary="Delete a Tenant by Wallet ID", status_code=204)
async def delete_tenant_by_id(
    wallet_id: str,
    group_id: Optional[str] = group_id_query,
    admin_auth: AcaPyAuthVerified = Depends(acapy_auth_tenant_admin),
) -> None:
    """
    Delete Tenant by ID
    ---

    Use this endpoint to delete a Tenant by its Wallet ID. This action will remove the Tenant's Wallet,
    along with any associated credentials, connections, and other data. If the tenant is an issuer or verifier,
    they will also be removed from the trust registry.

    Request parameters:
    ---
        wallet_id: str
            The Wallet ID of the Tenant to delete.

    Response body:
    ---
        status_code: 204 No Content
    """
    bound_logger = logger.bind(body={"wallet_id": wallet_id})
    bound_logger.debug("DELETE request received: Deleting tenant by id")

    async with get_tenant_admin_controller(admin_auth) as admin_controller:
        await get_wallet_and_assert_valid_group(
            admin_controller=admin_controller,
            wallet_id=wallet_id,
            group_id=group_id,
            logger=bound_logger,
        )

        # wallet_id is the id of the actor in the trust registry.
        # This makes it a lot easier to link a tenant to an actor
        # in the trust registry, especially if the tenant does not have
        # a public did.
        bound_logger.debug("Retrieving tenant from trust registry")
        actor = await fetch_actor_by_id(wallet_id)

        # Remove actor if found
        if actor:
            bound_logger.debug("Actor found, removing from trust registry")
            await remove_actor_by_id(wallet_id)

        bound_logger.debug("Deleting wallet")
        await handle_acapy_call(
            logger=bound_logger,
            acapy_call=admin_controller.multitenancy.delete_wallet,
            wallet_id=wallet_id,
        )
        bound_logger.debug("Successfully deleted tenant.")


@router.get(
    "/{wallet_id}/access-token",
    response_model=TenantAuth,
    summary="Update auth token by Wallet ID",
    deprecated=True,
)
async def get_wallet_auth_token(
    wallet_id: str,
    group_id: Optional[str] = group_id_query,
    admin_auth: AcaPyAuthVerified = Depends(acapy_auth_tenant_admin),
) -> TenantAuth:
    """
    Rotate Wallet access token by ID
    ---

    Calling this endpoint will invalidate the previous access token for the Wallet.

    Request parameters:
    ---
        wallet_id: str
            The Wallet ID of the tenant for which the access token will be rotated.

    Response body:
    ---
        TenantAuth
            access_token: str
                The new access token for the Wallet.
    """
    bound_logger = logger.bind(body={"wallet_id": wallet_id})
    bound_logger.debug("GET request received: Access token for tenant")

    async with get_tenant_admin_controller(admin_auth) as admin_controller:
        await get_wallet_and_assert_valid_group(
            admin_controller=admin_controller,
            wallet_id=wallet_id,
            group_id=group_id,
            logger=bound_logger,
        )

        bound_logger.debug("Getting auth token for wallet")
        response = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=admin_controller.multitenancy.get_auth_token,
            wallet_id=wallet_id,
            body=CreateWalletTokenRequest(),
        )

    response = TenantAuth(access_token=tenant_api_key(response.token))
    bound_logger.debug("Successfully retrieved access token.")
    return response


@router.post(
    "/{wallet_id}/access-token",
    response_model=TenantAuth,
    summary="Update auth token by Wallet ID",
)
async def get_wallet_auth_token(
    wallet_id: str,
    group_id: Optional[str] = group_id_query,
    admin_auth: AcaPyAuthVerified = Depends(acapy_auth_tenant_admin),
) -> TenantAuth:
    """
    Rotate Wallet access token by ID
    ---

    Calling this endpoint will invalidate the previous access token for the Wallet.

    Request parameters:
    ---
        wallet_id: str
            The Wallet ID of the tenant for which the access token will be rotated.

    Response body:
    ---
        TenantAuth
            access_token: str
                The new access token for the Wallet.
    """
    bound_logger = logger.bind(body={"wallet_id": wallet_id})
    bound_logger.debug("GET request received: Access token for tenant")

    async with get_tenant_admin_controller(admin_auth) as admin_controller:
        await get_wallet_and_assert_valid_group(
            admin_controller=admin_controller,
            wallet_id=wallet_id,
            group_id=group_id,
            logger=bound_logger,
        )

        bound_logger.debug("Getting auth token for wallet")
        response = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=admin_controller.multitenancy.get_auth_token,
            wallet_id=wallet_id,
            body=CreateWalletTokenRequest(),
        )

    response = TenantAuth(access_token=tenant_api_key(response.token))
    bound_logger.debug("Successfully retrieved access token.")
    return response


@router.put("/{wallet_id}", response_model=Tenant, summary="Update Tenant by Wallet ID")
async def update_tenant(
    wallet_id: str,
    body: UpdateTenantRequest,
    group_id: Optional[str] = group_id_query,
    admin_auth: AcaPyAuthVerified = Depends(acapy_auth_tenant_admin),
) -> Tenant:
    """
    Update Tenant by Wallet ID
    ---

    Update a Tenant's details based on their Wallet ID.

    Holders cannot have their roles updated. Attempting to assign issuer or verifier
    roles to a holder will result in a 409 conflict error.

    Only issuers or verifiers can be updated to hold both roles.

    This endpoint does not support revoking roles from issuers or verifiers.

    Updates to `image_url` for issuers and verifiers will be reflected on the trust registry.


    Request body:
    ---
        body: UpdateTenantRequest
            wallet_label: Optional[str]
                An optional alias for the Tenant.
            roles: Optional[List[str]]
                A list of roles to assign to the Tenant.
            image_url: Optional[str]
                An optional image URL for the Tenant.
            extra_settings: Optional[Dict[str, Union[bool, str]]]
                Optional per-tenant settings to configure wallet behaviour for advanced users.

    Response body:
    ---
        Tenant
            wallet_id: str
            wallet_label: str
            wallet_name: str
            created_at: str
            updated_at: Optional[str]
            image_url: Optional[str]
            group_id: Optional[str]
    """
    bound_logger = logger.bind(body={"wallet_id": wallet_id, "body": body})
    bound_logger.debug("PUT request received: Update tenant")

    async with get_tenant_admin_controller(admin_auth) as admin_controller:
        await get_wallet_and_assert_valid_group(
            admin_controller=admin_controller,
            wallet_id=wallet_id,
            group_id=group_id,
            logger=bound_logger,
        )

        wallet = await handle_tenant_update(
            admin_controller=admin_controller, wallet_id=wallet_id, update_request=body
        )

    response = tenant_from_wallet_record(wallet)
    bound_logger.debug("Successfully updated tenant.")
    return response


@router.get("/{wallet_id}", response_model=Tenant, summary="Get Tenant by wallet ID")
async def get_tenant(
    wallet_id: str,
    group_id: Optional[str] = group_id_query,
    admin_auth: AcaPyAuthVerified = Depends(acapy_auth_tenant_admin),
) -> Tenant:
    """
    Fetch Tenant info by ID
    ---

    Use this endpoint to fetch Tenant info by its Wallet ID.

    Request parameters:
    ---
        wallet_id: str
            The Wallet ID of the Tenant to fetch.

    Response body:
    ---
        Tenant
            wallet_id: str
            wallet_label: str
            wallet_name: str
            created_at: str
            updated_at: Optional[str]
            image_url: Optional[str]
            group_id: Optional[str]
    """
    bound_logger = logger.bind(body={"wallet_id": wallet_id})
    bound_logger.debug("GET request received: Fetch tenant by id")

    async with get_tenant_admin_controller(admin_auth) as admin_controller:
        wallet = await get_wallet_and_assert_valid_group(
            admin_controller=admin_controller,
            wallet_id=wallet_id,
            group_id=group_id,
            logger=bound_logger,
        )

    response = tenant_from_wallet_record(wallet)
    bound_logger.debug("Successfully fetched tenant from wallet record.")
    return response


@router.get("", response_model=List[Tenant], summary="Fetch All Tenants (Paginated)")
async def get_tenants(
    wallet_name: Optional[str] = None,
    group_id: Optional[str] = group_id_query,
    limit: Optional[int] = limit_query_parameter,
    offset: Optional[int] = offset_query_parameter,
    order_by: Optional[str] = order_by_query_parameter,
    descending: bool = descending_query_parameter,
    admin_auth: AcaPyAuthVerified = Depends(acapy_auth_tenant_admin),
) -> List[Tenant]:
    """
    Fetch all Tenants, or Fetch by Wallet Name
    ---

    Use this endpoint to fetch all tenants, or filter by wallet name and/or group ID.

    The default for `limit` is 1000.

    Results are ordered by record created time.

    Optional Request parameters:
    ---
        wallet_name: str
            Filter by wallet name.
        limit: int
            Number of results to return.
        offset: int
            Number of results to skip.
        descending: bool
            Whether to return results in descending order.


    Response body:
    ---
        List[Tenant]
            wallet_id: str
            wallet_label: str
            wallet_name: str
            created_at: str
            updated_at: Optional[str]
            image_url: Optional[str]
            group_id: Optional[str]
    """
    bound_logger = logger.bind(body={"wallet_name": wallet_name, "group_id": group_id})
    bound_logger.debug(
        "GET request received: Fetch tenants by wallet name and/or group id"
    )

    async with get_tenant_admin_controller(admin_auth) as admin_controller:
        wallets = await handle_acapy_call(
            logger=bound_logger,
            acapy_call=admin_controller.multitenancy.get_wallets,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
            wallet_name=wallet_name,
            group_id=group_id,
        )

    wallets_list = wallets.results

    if not wallets_list:
        bound_logger.debug("No wallets found.")
        return []

    response = [tenant_from_wallet_record(record) for record in wallets_list]
    bound_logger.debug("Successfully fetched wallets.")
    return response
