import pytest
from aries_cloudcontroller.acapy_client import AcaPyClient
from fastapi import HTTPException
from uuid_utils import uuid4

import app.services.trust_registry.actors as trust_registry
from app.dependencies.acapy_clients import get_tenant_controller
from app.routes.admin.tenants import router
from app.services import acapy_wallet
from app.tests.util.regression_testing import TestMode
from app.util.did import ed25519_verkey_to_did_key
from shared import RichAsyncClient

TENANTS_BASE_PATH = router.prefix

skip_regression_test_reason = "Don't need to cover tenant tests in regression mode"

group_id = "TestGroup"


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_post_wallet_auth_token(tenant_admin_client: RichAsyncClient):
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.ca",
            "wallet_label": uuid4().hex,
            "group_id": group_id,
        },
    )

    assert response.status_code == 200

    tenant = response.json()
    wallet_id = tenant["wallet_id"]

    try:
        # Attempting to access with incorrect wallet_id will fail with 404
        with pytest.raises(HTTPException) as exc:
            await tenant_admin_client.post(
                f"{TENANTS_BASE_PATH}/bad_wallet_id/access-token"
            )
        assert exc.value.status_code == 404

        # Attempting to access with incorrect group_id will fail with 404
        with pytest.raises(HTTPException) as exc:
            await tenant_admin_client.post(
                f"{TENANTS_BASE_PATH}/{wallet_id}/access-token?group_id=wrong_group"
            )
        assert exc.value.status_code == 404

        # Successfully get access-token with correct group_id
        response = await tenant_admin_client.post(
            f"{TENANTS_BASE_PATH}/{wallet_id}/access-token?group_id={group_id}"
        )
        assert response.status_code == 200

        token = response.json()

        assert token["access_token"]
        assert token["access_token"].startswith("tenant.ey")
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_create_tenant_member_wo_wallet_name(
    tenant_admin_client: RichAsyncClient, tenant_admin_acapy_client: AcaPyClient
):
    wallet_label = uuid4().hex
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.ca",
            "wallet_label": wallet_label,
            "group_id": group_id,
        },
    )

    assert response.status_code == 200

    tenant = response.json()
    wallet_id = tenant["wallet_id"]

    try:
        wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
            wallet_id=wallet_id
        )

        wallet_name = wallet.settings["wallet.name"]
        assert wallet_id == wallet.wallet_id
        assert tenant["group_id"] == group_id
        assert tenant["wallet_label"] == wallet_label
        assert tenant["created_at"] == wallet.created_at
        assert tenant["updated_at"] == wallet.updated_at
        assert tenant["wallet_name"] == wallet_name
        assert len(wallet_name) == 32
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_create_tenant_member_w_wallet_name(
    tenant_admin_client: RichAsyncClient, tenant_admin_acapy_client: AcaPyClient
):
    wallet_label = uuid4().hex
    wallet_name = "TestWalletName"
    create_tenant_payload = {
        "image_url": "https://image.ca",
        "wallet_label": wallet_label,
        "group_id": group_id,
        "wallet_name": wallet_name,
    }

    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json=create_tenant_payload,
    )

    assert response.status_code == 200

    tenant = response.json()
    wallet_id = tenant["wallet_id"]

    try:
        wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
            wallet_id=wallet_id
        )

        assert wallet_id == wallet.wallet_id
        assert tenant["group_id"] == group_id
        assert tenant["wallet_label"] == wallet_label
        assert tenant["created_at"] == wallet.created_at
        assert tenant["updated_at"] == wallet.updated_at
        assert tenant["wallet_name"] == wallet_name
        assert wallet.settings["wallet.name"] == wallet_name

        with pytest.raises(HTTPException) as http_error:
            await tenant_admin_client.post(
                TENANTS_BASE_PATH,
                json=create_tenant_payload,
            )
        assert http_error.value.status_code == 409
        assert "already exists" in http_error.value.detail
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
@pytest.mark.xdist_group(name="issuer_test_group_5")
async def test_create_tenant_issuer(
    tenant_admin_client: RichAsyncClient,
    tenant_admin_acapy_client: AcaPyClient,
):
    wallet_label = uuid4().hex
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.ca",
            "wallet_label": wallet_label,
            "roles": ["issuer"],
            "group_id": group_id,
        },
    )
    assert response.status_code == 200

    tenant = response.json()
    wallet_id = tenant["wallet_id"]

    try:
        actor = await trust_registry.fetch_actor_by_id(wallet_id)
        if not actor:
            pytest.fail("Missing actor")

        acapy_token: str = tenant["access_token"].split(".", 1)[1]
        async with get_tenant_controller(acapy_token) as tenant_controller:
            public_did = await acapy_wallet.get_public_did(tenant_controller)

        # Actor
        assert actor.name == tenant["wallet_label"]
        assert actor.did == public_did.did
        assert actor.roles == ["issuer"]

        # Tenant
        wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
            wallet_id=wallet_id
        )
        assert tenant["wallet_id"] == wallet.wallet_id
        assert tenant["wallet_label"] == wallet_label
        assert tenant["created_at"] == wallet.created_at
        assert tenant["updated_at"] == wallet.updated_at
        assert len(wallet.settings["wallet.name"]) == 32

        # Assert that wallet_label cannot be re-used by plain tenants
        with pytest.raises(HTTPException) as http_error:
            await tenant_admin_client.post(
                TENANTS_BASE_PATH,
                json={"wallet_label": wallet_label},
            )

            assert http_error.status_code == 409
            assert "Can't create Tenant." in http_error.json()["details"]
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_create_tenant_verifier(
    tenant_admin_client: RichAsyncClient, tenant_admin_acapy_client: AcaPyClient
):
    wallet_label = uuid4().hex
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.ca",
            "wallet_label": wallet_label,
            "roles": ["verifier"],
        },
    )
    assert response.status_code == 200

    tenant = response.json()
    wallet_id = tenant["wallet_id"]

    try:
        wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
            wallet_id=wallet_id
        )

        actor = await trust_registry.fetch_actor_by_id(wallet_id)

        if not actor:
            pytest.fail("Missing actor")

        acapy_token: str = tenant["access_token"].split(".", 1)[1]

        async with get_tenant_controller(acapy_token) as tenant_controller:
            connections = await tenant_controller.connection.get_connections(
                alias=f"Trust Registry {wallet_label}"
            )

        connection = connections.results[0]

        # Connection invitation
        assert connection.state == "invitation"

        assert actor.name == tenant["wallet_label"]
        assert actor.did == ed25519_verkey_to_did_key(connection.invitation_key)
        assert actor.roles == ["verifier"]

        # Tenant
        assert tenant["wallet_id"] == wallet.wallet_id
        assert tenant["wallet_label"] == wallet_label
        assert tenant["created_at"] == wallet.created_at
        assert tenant["updated_at"] == wallet.updated_at
        assert len(wallet.settings["wallet.name"]) == 32
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
@pytest.mark.xdist_group(name="issuer_test_group_5")
async def test_update_tenant_verifier_to_issuer(
    tenant_admin_client: RichAsyncClient,
    tenant_admin_acapy_client: AcaPyClient,
):
    wallet_label = uuid4().hex
    image_url = "https://image.ca"
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": image_url,
            "wallet_label": wallet_label,
            "roles": ["verifier"],
            "group_id": group_id,
        },
    )

    verifier_tenant = response.json()
    verifier_wallet_id = verifier_tenant["wallet_id"]

    try:
        verifier_actor = await trust_registry.fetch_actor_by_id(verifier_wallet_id)
        assert verifier_actor
        assert verifier_actor.name == wallet_label
        assert verifier_actor.roles == ["verifier"]

        wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
            wallet_id=verifier_wallet_id
        )
        assert len(wallet.settings["wallet.name"]) == 32

        acapy_token: str = verifier_tenant["access_token"].split(".", 1)[1]

        async with get_tenant_controller(acapy_token) as tenant_controller:
            connections = await tenant_controller.connection.get_connections(
                alias=f"Trust Registry {wallet_label}"
            )

        connection = connections.results[0]

        # Connection invitation
        assert connection.state == "invitation"
        assert verifier_actor.did == ed25519_verkey_to_did_key(
            connection.invitation_key
        )

        # Tenant
        assert verifier_tenant["wallet_id"] == wallet.wallet_id
        assert verifier_tenant["image_url"] == image_url
        assert verifier_tenant["wallet_label"] == wallet_label
        assert verifier_tenant["created_at"] == wallet.created_at
        assert verifier_tenant["updated_at"] == wallet.updated_at

        new_wallet_label = uuid4().hex
        new_image_url = "https://some-ssi-site.org/image.png"
        new_roles = ["issuer", "verifier"]

        json_request = {
            "image_url": new_image_url,
            "wallet_label": new_wallet_label,
            "roles": new_roles,
        }
        # Attempting to update with incorrect wallet_id will fail with 404
        with pytest.raises(HTTPException) as exc:
            await tenant_admin_client.put(
                f"{TENANTS_BASE_PATH}/bad_wallet_id", json=json_request
            )
        assert exc.value.status_code == 404

        # Attempting to update with incorrect group_id will fail with 404
        with pytest.raises(HTTPException) as exc:
            await tenant_admin_client.put(
                f"{TENANTS_BASE_PATH}/{verifier_wallet_id}?group_id=wrong_group",
                json=json_request,
            )
        assert exc.value.status_code == 404

        # Successful update with correct group
        update_response = await tenant_admin_client.put(
            f"{TENANTS_BASE_PATH}/{verifier_wallet_id}?group_id={group_id}",
            json=json_request,
        )
        new_tenant = update_response.json()
        assert new_tenant["wallet_id"] == wallet.wallet_id
        assert new_tenant["image_url"] == new_image_url
        assert new_tenant["wallet_label"] == new_wallet_label
        assert new_tenant["created_at"] == wallet.created_at
        assert new_tenant["group_id"] == group_id

        new_actor = await trust_registry.fetch_actor_by_id(verifier_wallet_id)

        acapy_token = (
            (
                await tenant_admin_client.post(
                    f"{TENANTS_BASE_PATH}/{verifier_wallet_id}/access-token"
                )
            )
            .json()["access_token"]
            .split(".", 1)[1]
        )

        async with get_tenant_controller(acapy_token) as tenant_controller:
            public_did = await acapy_wallet.get_public_did(tenant_controller)
            assert public_did

        assert new_actor
        assert new_actor.name == new_wallet_label
        assert new_actor.did == new_actor.did
        assert set(new_actor.roles) == {"issuer", "verifier"}
        assert new_actor.image_url == new_image_url

        assert new_actor.didcomm_invitation is not None
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{verifier_wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_tenants(tenant_admin_client: RichAsyncClient):
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.ca",
            "wallet_label": uuid4().hex,
        },
    )

    assert response.status_code == 200
    created_tenant = response.json()
    first_wallet_id = created_tenant["wallet_id"]
    wallet_ids = [first_wallet_id]

    try:
        response = await tenant_admin_client.get(
            f"{TENANTS_BASE_PATH}/{first_wallet_id}"
        )

        assert response.status_code == 200
        retrieved_tenant = response.json()
        created_tenant.pop("access_token")
        assert created_tenant == retrieved_tenant

        response = await tenant_admin_client.post(
            TENANTS_BASE_PATH,
            json={
                "image_url": "https://image.ca",
                "wallet_label": uuid4().hex,
                "group_id": group_id,
            },
        )

        assert response.status_code == 200
        last_wallet_id = response.json()["wallet_id"]
        wallet_ids += (last_wallet_id,)

        response = await tenant_admin_client.get(
            TENANTS_BASE_PATH, params={"group_id": group_id}
        )
        assert response.status_code == 200
        tenants = response.json()
        assert len(tenants) >= 1

        # Make sure created tenant is returned
        assert any(tenant["wallet_id"] == last_wallet_id for tenant in tenants)
        assert all(tenant["group_id"] == group_id for tenant in tenants)
    finally:
        # Cleanup: Delete the created tenant even if test fails
        for wallet_id in wallet_ids:
            delete_response = await tenant_admin_client.delete(
                f"{TENANTS_BASE_PATH}/{wallet_id}"
            )
            assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_tenants_by_group(tenant_admin_client: RichAsyncClient):
    wallet_label = uuid4().hex
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.ca",
            "wallet_label": wallet_label,
            "group_id": group_id,
        },
    )

    assert response.status_code == 200
    created_tenant = response.json()
    wallet_id = created_tenant["wallet_id"]

    try:
        response = await tenant_admin_client.get(
            f"{TENANTS_BASE_PATH}?group_id={group_id}"
        )
        assert response.status_code == 200
        tenants = response.json()
        assert len(tenants) >= 1

        # Make sure created tenant is returned
        assert any(tenant["wallet_id"] == wallet_id for tenant in tenants)
        assert all(tenant["group_id"] == group_id for tenant in tenants)

        response = await tenant_admin_client.get(f"{TENANTS_BASE_PATH}?group_id=other")
        assert response.status_code == 200
        tenants = response.json()
        assert len(tenants) == 0
        assert tenants == []
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_tenants_by_wallet_name(tenant_admin_client: RichAsyncClient):
    wallet_name = uuid4().hex
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.ca",
            "wallet_label": "abc",
            "wallet_name": wallet_name,
            "group_id": group_id,
        },
    )

    assert response.status_code == 200
    created_tenant = response.json()
    wallet_id = created_tenant["wallet_id"]

    try:
        response = await tenant_admin_client.get(
            f"{TENANTS_BASE_PATH}?wallet_name={wallet_name}"
        )
        assert response.status_code == 200
        tenants = response.json()
        assert len(tenants) == 1
        tenant = tenants[0]

        # Make sure created tenant is returned
        assert tenant["wallet_id"] == wallet_id
        assert tenant["group_id"] == group_id

        # Does not return when wallet_name = other
        response = await tenant_admin_client.get(
            f"{TENANTS_BASE_PATH}?wallet_name=other"
        )
        assert response.status_code == 200
        tenants = response.json()
        assert len(tenants) == 0
        assert tenants == []

        # Does not return when group_id = other
        response = await tenant_admin_client.get(
            f"{TENANTS_BASE_PATH}?wallet_name={wallet_name}&group_id=other"
        )
        assert response.status_code == 200
        tenants = response.json()
        assert len(tenants) == 0
        assert tenants == []
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_tenant(tenant_admin_client: RichAsyncClient):
    wallet_name = uuid4().hex
    wallet_label = "abc"
    image_url = "https://image.ca"
    create_response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": image_url,
            "wallet_label": wallet_label,
            "wallet_name": wallet_name,
            "group_id": group_id,
        },
    )

    assert create_response.status_code == 200
    created_tenant = create_response.json()
    wallet_id = created_tenant["wallet_id"]

    try:
        # Attempting to get with incorrect wallet_id will fail with 404
        with pytest.raises(HTTPException) as exc:
            await tenant_admin_client.get(f"{TENANTS_BASE_PATH}/bad_wallet_id")
        assert exc.value.status_code == 404

        # Attempting to get with incorrect group_id will fail with 404
        with pytest.raises(HTTPException) as exc:
            await tenant_admin_client.get(
                f"{TENANTS_BASE_PATH}/{wallet_id}?group_id=wrong_group"
            )
        assert exc.value.status_code == 404

        # Successful get with correct group_id
        get_tenant_response = await tenant_admin_client.get(
            f"{TENANTS_BASE_PATH}/{wallet_id}?group_id={group_id}"
        )
        assert get_tenant_response.status_code == 200
        tenant = get_tenant_response.json()

        assert tenant["wallet_id"] == wallet_id
        assert tenant["wallet_label"] == wallet_label
        assert tenant["wallet_name"] == wallet_name
        assert tenant["image_url"] == image_url
        assert tenant["group_id"] == group_id
        assert tenant["created_at"] == created_tenant["created_at"]
        assert tenant["updated_at"] == created_tenant["updated_at"]
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_delete_tenant(
    tenant_admin_client: RichAsyncClient, tenant_admin_acapy_client: AcaPyClient
):
    wallet_label = uuid4().hex
    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.ca",
            "wallet_label": wallet_label,
            "roles": ["verifier"],
            "group_id": group_id,
        },
    )

    assert response.status_code == 200
    tenant = response.json()
    wallet_id = tenant["wallet_id"]

    # Actor exists
    actor = await trust_registry.fetch_actor_by_id(wallet_id)
    assert actor

    # Attempting to delete with incorrect wallet_id will fail with 404
    with pytest.raises(HTTPException) as exc:
        await tenant_admin_client.delete(f"{TENANTS_BASE_PATH}/bad_wallet_id")
    assert exc.value.status_code == 404

    # Attempting to delete with incorrect group_id will fail with 404
    with pytest.raises(HTTPException) as exc:
        await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{wallet_id}?group_id=wrong_group"
        )
    assert exc.value.status_code == 404

    # Successful delete with correct group_id:
    response = await tenant_admin_client.delete(
        f"{TENANTS_BASE_PATH}/{wallet_id}?group_id={group_id}"
    )
    assert response.status_code == 204

    # Actor doesn't exist any more
    actor = await trust_registry.fetch_actor_by_id(wallet_id)
    assert not actor

    with pytest.raises(Exception):
        await tenant_admin_acapy_client.multitenancy.get_wallet(wallet_id=wallet_id)


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_extra_settings(
    tenant_admin_client: RichAsyncClient, tenant_admin_acapy_client: AcaPyClient
):
    # Create tenant with custom wallet settings
    created_tenant_response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "wallet_label": uuid4().hex,
            "extra_settings": {"ACAPY_AUTO_ACCEPT_INVITES": True},
        },
    )
    assert created_tenant_response.status_code == 200
    created_wallet_id = created_tenant_response.json()["wallet_id"]

    try:
        # Fetch wallet record and assert setting got passed through
        wallet_record = await tenant_admin_acapy_client.multitenancy.get_wallet(
            wallet_id=created_wallet_id
        )
        assert wallet_record.settings["debug.auto_accept_invites"] is True

        # Test updating a wallet setting
        update_tenant_response = await tenant_admin_client.put(
            f"{TENANTS_BASE_PATH}/{created_wallet_id}",
            json={
                "wallet_label": "new_label",
                "extra_settings": {"ACAPY_AUTO_ACCEPT_INVITES": False},
            },
        )
        assert update_tenant_response.status_code == 200

        # Fetch updated wallet record and assert setting got updated
        updated_wallet_record = await tenant_admin_acapy_client.multitenancy.get_wallet(
            wallet_id=created_wallet_id
        )
        assert updated_wallet_record.settings["debug.auto_accept_invites"] is False

        # Assert bad request is raised for invalid extra_settings
        with pytest.raises(Exception):
            bad_response = await tenant_admin_client.post(
                TENANTS_BASE_PATH,
                json={
                    "wallet_label": uuid4().hex,
                    "extra_settings": {"Bad_value": True},
                },
            )

            assert bad_response.status_code == 422
    finally:
        # Cleanup: Delete the created tenant even if test fails
        delete_response = await tenant_admin_client.delete(
            f"{TENANTS_BASE_PATH}/{created_wallet_id}"
        )
        assert delete_response.status_code == 204


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_create_tenant_validation(tenant_admin_client: RichAsyncClient):
    # Assert that 422 is raised when unacceptable special chars are used in wallet label or name
    # The following chars are either reserved or unsafe to use in URIs without encoding
    for char in [
        "#",
        "%",
        "^",
        "&",
        "+",
        "=",
        "{",
        "}",
        "[",
        "]",
        "|",
        "\\",
        '"',
        ":",
        ";",
        ",",
        "/",
        "?",
    ]:
        # Assert bad requests for wallet label
        with pytest.raises(Exception):
            bad_label_response = await tenant_admin_client.post(
                TENANTS_BASE_PATH,
                json={"wallet_label": uuid4().hex + char},
            )

            assert bad_label_response.status_code == 422
            assert "wallet_label" in bad_label_response.json()

        # Assert bad requests for wallet name
        with pytest.raises(Exception):
            bad_name_response = await tenant_admin_client.post(
                TENANTS_BASE_PATH,
                json={"wallet_label": uuid4().hex, "wallet_name": char},
            )

            assert bad_name_response.status_code == 422
            assert "wallet_name" in bad_label_response.json()

        # Assert bad requests for group_id
        with pytest.raises(Exception):
            bad_group_response = await tenant_admin_client.post(
                TENANTS_BASE_PATH,
                json={"wallet_label": uuid4().hex, "group_id": char},
            )

            assert bad_group_response.status_code == 422
            assert "group_id" in bad_group_response.json()

    # Lastly, assert very long strings (> 100 chars) aren't allowed
    very_long_string = 101 * "a"

    # for wallet label
    with pytest.raises(Exception):
        bad_label_response = await tenant_admin_client.post(
            TENANTS_BASE_PATH,
            json={"wallet_label": very_long_string},
        )

        assert bad_label_response.status_code == 422
        assert "wallet_label" in bad_label_response.json()

    # for wallet name
    with pytest.raises(Exception):
        bad_name_response = await tenant_admin_client.post(
            TENANTS_BASE_PATH,
            json={"wallet_label": uuid4().hex, "wallet_name": very_long_string},
        )

        assert bad_name_response.status_code == 422
        assert "wallet_name" in bad_label_response.json()


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_wallets_paginated(tenant_admin_client: RichAsyncClient):
    num_wallets_to_test = 5
    test_group = "TestPaginationGroup"
    wallet_names = []

    try:
        # Create multiple wallets
        for _ in range(num_wallets_to_test):
            wallet_name = uuid4().hex
            wallet_names.append(wallet_name)
            response = await tenant_admin_client.post(
                TENANTS_BASE_PATH,
                json={
                    "image_url": "https://image.ca",
                    "wallet_name": wallet_name,
                    "wallet_label": "test_wallet",
                    "group_id": test_group,
                },
            )

        # Test different limits
        for limit in range(1, num_wallets_to_test + 2):
            response = await tenant_admin_client.get(
                TENANTS_BASE_PATH,
                params={"limit": limit, "group_id": test_group},
            )
            wallets = response.json()
            assert len(wallets) == min(limit, num_wallets_to_test)

        # Test ascending order
        response = await tenant_admin_client.get(
            TENANTS_BASE_PATH,
            params={
                "limit": num_wallets_to_test,
                "group_id": test_group,
                "descending": False,
            },
        )
        wallets_asc = response.json()
        assert len(wallets_asc) == num_wallets_to_test

        # Verify that the wallets are in ascending order based on created_at
        assert wallets_asc == sorted(wallets_asc, key=lambda x: x["created_at"])

        # Test descending order
        response = await tenant_admin_client.get(
            TENANTS_BASE_PATH,
            params={
                "limit": num_wallets_to_test,
                "group_id": test_group,
                "descending": True,
            },
        )
        wallets_desc = response.json()
        assert len(wallets_desc) == num_wallets_to_test

        # Verify that the wallets are in descending order based on created_at
        assert wallets_desc == sorted(
            wallets_desc, key=lambda x: x["created_at"], reverse=True
        )

        # Compare ascending and descending order results
        assert wallets_desc == sorted(
            wallets_asc, key=lambda x: x["created_at"], reverse=True
        )

        # Test offset greater than number of records
        response = await tenant_admin_client.get(
            TENANTS_BASE_PATH,
            params={"limit": 1, "offset": num_wallets_to_test, "group_id": test_group},
        )
        wallets = response.json()
        assert len(wallets) == 0

        # Test fetching unique records with pagination
        prev_wallets = []
        for offset in range(num_wallets_to_test):
            response = await tenant_admin_client.get(
                TENANTS_BASE_PATH,
                params={"limit": 1, "offset": offset, "group_id": test_group},
            )

            wallets = response.json()
            assert len(wallets) == 1

            wallet = wallets[0]
            assert wallet not in prev_wallets
            prev_wallets.append(wallet)

        # Test invalid limit and offset values
        invalid_params = [
            {"limit": -1},  # must be positive
            {"offset": -1},  # must be positive
            {"limit": 0},  # must be greater than 0
            {"limit": 10001},  # must be less than or equal to max in ACA-Py: 10'000
        ]

        for params in invalid_params:
            with pytest.raises(HTTPException) as exc:
                await tenant_admin_client.get(TENANTS_BASE_PATH, params=params)
            assert exc.value.status_code == 422
    finally:
        # Cleanup: Delete the created tenants even if test fails
        for wallet_name in wallet_names:
            response = await tenant_admin_client.get(
                f"{TENANTS_BASE_PATH}?wallet_name={wallet_name}&group_id={test_group}"
            )
            wallet_id = response.json()[0]["wallet_id"]
            await tenant_admin_client.delete(f"{TENANTS_BASE_PATH}/{wallet_id}")
