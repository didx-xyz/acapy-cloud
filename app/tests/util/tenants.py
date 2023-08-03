from app.models.tenants import CreateTenantRequest, CreateTenantResponse
from app.util.string import random_string
from shared import RichAsyncClient, parse_with_error_handling
from app.routes.admin.tenants import router

ADMIN_BASE_PATH = router.prefix

def append_random_string(name):
    return f"{name}_{random_string(5)}"


async def post_tenant_request(
    admin_client: RichAsyncClient, request: CreateTenantRequest
) -> CreateTenantResponse:
    response = await admin_client.post(ADMIN_BASE_PATH, json=request.dict())
    return parse_with_error_handling(CreateTenantResponse, response.text)


async def create_issuer_tenant(admin_client: RichAsyncClient, name: str):
    request = CreateTenantRequest(
        name=append_random_string(name), roles=["issuer"], group_id="IssuerGroup"
    )
    return await post_tenant_request(admin_client, request)


async def create_verifier_tenant(admin_client: RichAsyncClient, name: str):
    request = CreateTenantRequest(
        name=append_random_string(name),
        roles=["verifier"],
        group_id="VerifierGroup",
    )
    return await post_tenant_request(admin_client, request)


async def create_tenant(admin_client: RichAsyncClient, name: str):
    request = CreateTenantRequest(
        image_url="https://aries.ca/images/sample.png",
        name=append_random_string(name),
        group_id="TenantGroup",
    )
    return await post_tenant_request(admin_client, request)


async def delete_tenant(admin_client: RichAsyncClient, tenant_id: str):
    await admin_client.delete(f"{ADMIN_BASE_PATH}/{tenant_id}")
