from typing import List, Literal

from aries_cloudcontroller import (
    AcaPyClient,
    UpdateWalletRequestWithGroupId,
    WalletRecordWithGroupId,
)
from fastapi.exceptions import HTTPException

from app.dependencies.acapy_clients import (
    get_governance_controller,
    get_tenant_controller,
)
from app.exceptions import (
    CloudApiException,
    handle_acapy_call,
    handle_model_with_validation,
)
from app.models.tenants import OnboardResult, UpdateTenantRequest
from app.services.onboarding.issuer import onboard_issuer
from app.services.onboarding.verifier import onboard_verifier
from app.services.trust_registry.actors import fetch_actor_by_id, update_actor
from shared.log_config import get_logger
from shared.models.trustregistry import TrustRegistryRole

logger = get_logger(__name__)


async def handle_tenant_update(
    admin_controller: AcaPyClient,
    wallet_id: str,
    update_request: UpdateTenantRequest,
) -> WalletRecordWithGroupId:
    bound_logger = logger.bind(body={"wallet_id": wallet_id})
    bound_logger.bind(body=update_request).debug("Handling tenant update")

    new_roles = update_request.roles or []
    new_label = update_request.wallet_label
    new_image_url = update_request.image_url

    # See if this wallet belongs to an actor
    actor = await fetch_actor_by_id(wallet_id)
    if not actor and new_roles:
        bound_logger.info(
            "Bad request: Tenant not found in trust registry. "
            "Holder tenants cannot be updated with new roles."
        )
        raise HTTPException(
            409,
            "Holder tenants cannot be updated with new roles. "
            "Only existing issuers or verifiers can have their role updated.",
        )

    if actor:
        existing_roles = actor.roles
        existing_image_url = actor.image_url
        added_roles = list(set(new_roles) - set(existing_roles))

        if new_label or added_roles or new_image_url:  # Only update actor if
            update_dict = {}
            if new_label:
                update_dict["name"] = new_label

            if added_roles:
                bound_logger.info("Updating tenant roles")
                # We need to pose as the tenant to onboard for the specified role
                token_response = await handle_acapy_call(
                    logger=bound_logger,
                    acapy_call=admin_controller.multitenancy.get_auth_token,
                    wallet_id=wallet_id,
                )

                onboard_result = await onboard_tenant(
                    tenant_label=new_label,
                    roles=added_roles,
                    wallet_auth_token=token_response.token,
                    wallet_id=wallet_id,
                )

                # Remove duplicates from the role list
                update_dict["roles"] = list(set(new_roles + existing_roles))
                update_dict["did"] = onboard_result.did
                update_dict["didcomm_invitation"] = onboard_result.didcomm_invitation

            if new_image_url and new_image_url != existing_image_url:
                update_dict["image_url"] = new_image_url

            updated_actor = actor.model_copy(update=update_dict)

            await update_actor(updated_actor)

    bound_logger.debug("Updating wallet")
    request_body = handle_model_with_validation(
        logger=bound_logger,
        model_class=UpdateWalletRequestWithGroupId,
        label=new_label,
        image_url=update_request.image_url,
        extra_settings=update_request.extra_settings,
    )
    wallet = await handle_acapy_call(
        logger=bound_logger,
        acapy_call=admin_controller.multitenancy.update_wallet,
        wallet_id=wallet_id,
        body=request_body,
    )
    bound_logger.debug("Tenant update handled successfully.")
    return wallet


async def onboard_tenant(
    *,
    tenant_label: str,
    roles: List[TrustRegistryRole],
    wallet_auth_token: str,
    wallet_id: str,
    did_method: Literal["sov", "cheqd"] = "sov",
) -> OnboardResult:
    bound_logger = logger.bind(
        body={"tenant_label": tenant_label, "roles": roles, "wallet_id": wallet_id}
    )
    bound_logger.bind(body=roles).debug("Start onboarding tenant")

    if "issuer" in roles:
        bound_logger.debug("Tenant has 'issuer' role, onboarding as issuer")
        # Get governance and tenant controllers, onboard issuer
        async with get_governance_controller() as governance_controller, get_tenant_controller(
            wallet_auth_token
        ) as tenant_controller:
            onboard_result = await onboard_issuer(
                endorser_controller=governance_controller,
                issuer_controller=tenant_controller,
                issuer_wallet_id=wallet_id,
                issuer_label=tenant_label,
                did_method=did_method,
            )
            bound_logger.debug("Onboarding as issuer completed successfully.")
            return onboard_result

    elif "verifier" in roles:
        bound_logger.debug("Tenant has 'verifier' role, onboarding as verifier")
        async with get_tenant_controller(wallet_auth_token) as tenant_controller:
            onboard_result = await onboard_verifier(
                verifier_label=tenant_label, verifier_controller=tenant_controller
            )
            bound_logger.debug("Onboarding as verifier completed successfully.")
            return onboard_result

    bound_logger.error("Tenant request does not have valid role(s) for onboarding.")
    raise CloudApiException("Unable to onboard tenant without role(s).")
