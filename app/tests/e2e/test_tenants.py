from uuid import uuid4

import pytest
from aries_cloudcontroller.acapy_client import AcaPyClient
from assertpy.assertpy import assert_that
from fastapi import HTTPException

import app.services.trust_registry.actors as trust_registry
from app.dependencies.acapy_clients import get_tenant_controller
from app.routes.admin.tenants import router
from app.services import acapy_wallet
from app.tests.util.regression_testing import TestMode
from app.util.did import ed25519_verkey_to_did_key
from shared import RichAsyncClient

TENANTS_BASE_PATH = router.prefix

skip_regression_test_reason = "Don't need to cover tenant tests in regression mode"


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_wallet_auth_token(tenant_admin_client: RichAsyncClient):
    group_id = "TestGroup"
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

    # Attempting to access with incorrect wallet_id will fail with 404
    with pytest.raises(HTTPException) as exc:
        await tenant_admin_client.get(f"{TENANTS_BASE_PATH}/bad_wallet_id/access-token")
    assert exc.value.status_code == 404

    # Attempting to access with incorrect group_id will fail with 404
    with pytest.raises(HTTPException) as exc:
        await tenant_admin_client.get(
            f"{TENANTS_BASE_PATH}/{wallet_id}/access-token?group_id=wrong_group"
        )
    assert exc.value.status_code == 404

    # Successfully get access-token with correct group_id
    response = await tenant_admin_client.get(
        f"{TENANTS_BASE_PATH}/{wallet_id}/access-token?group_id={group_id}"
    )
    assert response.status_code == 200

    token = response.json()

    assert token["access_token"]
    assert token["access_token"].startswith("tenant.ey")


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_create_tenant_member_wo_wallet_name(
    tenant_admin_client: RichAsyncClient, tenant_admin_acapy_client: AcaPyClient
):
    wallet_label = uuid4().hex
    group_id = "TestGroup"
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

    wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
        wallet_id=tenant["wallet_id"]
    )

    wallet_name = wallet.settings["wallet.name"]
    assert tenant["wallet_id"] == wallet.wallet_id
    assert tenant["group_id"] == group_id
    assert tenant["wallet_label"] == wallet_label
    assert tenant["created_at"] == wallet.created_at
    assert tenant["updated_at"] == wallet.updated_at
    assert tenant["wallet_name"] == wallet_name
    assert_that(wallet_name).is_length(32)


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
    group_id = "TestGroup"
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

    wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
        wallet_id=tenant["wallet_id"]
    )

    assert tenant["wallet_id"] == wallet.wallet_id
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

    # Delete created tenant
    delete_response = await tenant_admin_client.delete(
        f"{TENANTS_BASE_PATH}/{wallet.wallet_id}"
    )

    assert delete_response.status_code == 200


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_create_tenant_issuer(
    tenant_admin_client: RichAsyncClient,
    tenant_admin_acapy_client: AcaPyClient,
    governance_acapy_client: AcaPyClient,
):
    wallet_label = uuid4().hex
    group_id = "TestGroup"
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

    actor = await trust_registry.fetch_actor_by_id(wallet_id)
    if not actor:
        raise Exception("Missing actor")

    endorser_did = await acapy_wallet.get_public_did(governance_acapy_client)

    acapy_token: str = tenant["access_token"].split(".", 1)[1]
    async with get_tenant_controller(acapy_token) as tenant_controller:
        public_did = await acapy_wallet.get_public_did(tenant_controller)

        connections = await tenant_controller.connection.get_connections()

    connections = [
        connection
        for connection in connections.results
        if connection.their_public_did == endorser_did.did
    ]

    endorser_connection = connections[0]

    # Connection with endorser
    assert_that(endorser_connection).has_state("active")
    assert_that(endorser_connection).has_their_public_did(endorser_did.did)

    # Actor
    assert_that(actor).has_name(tenant["wallet_label"])
    assert_that(actor).has_did(f"did:sov:{public_did.did}")
    assert_that(actor).has_roles(["issuer"])

    # Tenant
    wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
        wallet_id=wallet_id
    )
    assert_that(tenant).has_wallet_id(wallet.wallet_id)
    assert_that(tenant).has_wallet_label(wallet_label)
    assert_that(tenant).has_created_at(wallet.created_at)
    assert_that(tenant).has_updated_at(wallet.updated_at)
    assert_that(wallet.settings["wallet.name"]).is_length(32)

    # Assert that wallet_label cannot be re-used by plain tenants
    with pytest.raises(HTTPException) as http_error:
        await tenant_admin_client.post(
            TENANTS_BASE_PATH,
            json={"wallet_label": wallet_label},
        )

        assert http_error.status_code == 409
        assert "Can't create Tenant." in http_error.json()["details"]


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

    wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
        wallet_id=wallet_id
    )

    actor = await trust_registry.fetch_actor_by_id(wallet_id)

    if not actor:
        raise Exception("Missing actor")

    acapy_token: str = tenant["access_token"].split(".", 1)[1]

    async with get_tenant_controller(acapy_token) as tenant_controller:
        connections = await tenant_controller.connection.get_connections(
            alias=f"Trust Registry {wallet_label}"
        )

    connection = connections.results[0]

    # Connection invitation
    assert_that(connection).has_state("invitation")

    assert_that(actor).has_name(tenant["wallet_label"])
    assert_that(actor).has_did(ed25519_verkey_to_did_key(connection.invitation_key))
    assert_that(actor).has_roles(["verifier"])

    # Tenant
    assert_that(tenant).has_wallet_id(wallet.wallet_id)
    assert_that(tenant).has_wallet_label(wallet_label)
    assert_that(tenant).has_created_at(wallet.created_at)
    assert_that(tenant).has_updated_at(wallet.updated_at)
    assert_that(wallet.settings["wallet.name"]).is_length(32)


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_update_tenant_verifier_to_issuer(
    tenant_admin_client: RichAsyncClient,
    tenant_admin_acapy_client: AcaPyClient,
    governance_acapy_client: AcaPyClient,
):
    wallet_label = uuid4().hex
    image_url = "https://image.ca"
    group_id = "TestGroup"
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
    verifier_actor = await trust_registry.fetch_actor_by_id(verifier_wallet_id)
    assert verifier_actor
    assert_that(verifier_actor).has_name(wallet_label)
    assert_that(verifier_actor).has_roles(["verifier"])

    wallet = await tenant_admin_acapy_client.multitenancy.get_wallet(
        wallet_id=verifier_wallet_id
    )
    assert_that(wallet.settings["wallet.name"]).is_length(32)

    acapy_token: str = verifier_tenant["access_token"].split(".", 1)[1]

    async with get_tenant_controller(acapy_token) as tenant_controller:
        connections = await tenant_controller.connection.get_connections(
            alias=f"Trust Registry {wallet_label}"
        )

    connection = connections.results[0]

    # Connection invitation
    assert_that(connection).has_state("invitation")
    assert_that(verifier_actor).has_did(
        ed25519_verkey_to_did_key(connection.invitation_key)
    )

    # Tenant
    assert_that(verifier_tenant).has_wallet_id(wallet.wallet_id)
    assert_that(verifier_tenant).has_image_url(image_url)
    assert_that(verifier_tenant).has_wallet_label(wallet_label)
    assert_that(verifier_tenant).has_created_at(wallet.created_at)
    assert_that(verifier_tenant).has_updated_at(wallet.updated_at)

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
    assert_that(new_tenant).has_wallet_id(wallet.wallet_id)
    assert_that(new_tenant).has_image_url(new_image_url)
    assert_that(new_tenant).has_wallet_label(new_wallet_label)
    assert_that(new_tenant).has_created_at(wallet.created_at)
    assert_that(new_tenant).has_group_id(group_id)

    new_actor = await trust_registry.fetch_actor_by_id(verifier_wallet_id)

    endorser_did = await acapy_wallet.get_public_did(governance_acapy_client)

    acapy_token = (
        (
            await tenant_admin_client.get(
                f"{TENANTS_BASE_PATH}/{verifier_wallet_id}/access-token"
            )
        )
        .json()["access_token"]
        .split(".", 1)[1]
    )

    async with get_tenant_controller(acapy_token) as tenant_controller:
        public_did = await acapy_wallet.get_public_did(tenant_controller)
        assert public_did

        _connections = (await tenant_controller.connection.get_connections()).results

        connections = [
            connection
            for connection in _connections
            if connection.their_public_did == endorser_did.did
        ]

    endorser_connection = connections[0]

    # Connection invitation
    assert_that(endorser_connection).has_state("active")
    assert_that(endorser_connection).has_their_public_did(endorser_did.did)

    assert new_actor
    assert_that(new_actor).has_name(new_wallet_label)
    assert_that(new_actor).has_did(f"{new_actor['did']}")
    assert_that(new_actor["roles"]).contains_only("issuer", "verifier")

    assert new_actor["didcomm_invitation"] is not None


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

    response = await tenant_admin_client.get(f"{TENANTS_BASE_PATH}/{first_wallet_id}")

    assert response.status_code == 200
    retrieved_tenant = response.json()
    created_tenant.pop("access_token")
    assert created_tenant == retrieved_tenant

    response = await tenant_admin_client.post(
        TENANTS_BASE_PATH,
        json={
            "image_url": "https://image.ca",
            "wallet_label": uuid4().hex,
            "group_id": "ac-dc",
        },
    )

    assert response.status_code == 200
    last_wallet_id = response.json()["wallet_id"]

    response = await tenant_admin_client.get(TENANTS_BASE_PATH)
    assert response.status_code == 200
    tenants = response.json()
    assert len(tenants) >= 1

    # Make sure created tenant is returned
    assert_that(tenants).extracting("wallet_id").contains(last_wallet_id)
    assert_that(tenants).extracting("group_id").contains("ac-dc")


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_tenants_by_group(tenant_admin_client: RichAsyncClient):
    wallet_label = uuid4().hex
    group_id = "group"
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

    response = await tenant_admin_client.get(f"{TENANTS_BASE_PATH}?group_id={group_id}")
    assert response.status_code == 200
    tenants = response.json()
    assert len(tenants) >= 1

    # Make sure created tenant is returned
    assert_that(tenants).extracting("wallet_id").contains(wallet_id)
    assert_that(tenants).extracting("group_id").contains(group_id)

    response = await tenant_admin_client.get(f"{TENANTS_BASE_PATH}?group_id=other")
    assert response.status_code == 200
    tenants = response.json()
    assert len(tenants) == 0
    assert tenants == []


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_tenants_by_wallet_name(tenant_admin_client: RichAsyncClient):
    wallet_name = uuid4().hex
    group_id = "group"
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

    response = await tenant_admin_client.get(
        f"{TENANTS_BASE_PATH}?wallet_name={wallet_name}"
    )
    assert response.status_code == 200
    tenants = response.json()
    assert len(tenants) == 1

    # Make sure created tenant is returned
    assert_that(tenants).extracting("wallet_id").contains(wallet_id)
    assert_that(tenants).extracting("group_id").contains(group_id)

    # Does not return when wallet_name = other
    response = await tenant_admin_client.get(f"{TENANTS_BASE_PATH}?wallet_name=other")
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


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_get_tenant(tenant_admin_client: RichAsyncClient):
    wallet_name = uuid4().hex
    wallet_label = "abc"
    image_url = "https://image.ca"
    group_id = "group"
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


@pytest.mark.anyio
@pytest.mark.skipif(
    TestMode.regression_run in TestMode.fixture_params,
    reason=skip_regression_test_reason,
)
async def test_delete_tenant(
    tenant_admin_client: RichAsyncClient, tenant_admin_acapy_client: AcaPyClient
):
    group_id = "delete_group"
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
    assert response.status_code == 200

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

    # Delete created tenant
    await tenant_admin_client.delete(f"{TENANTS_BASE_PATH}/{created_wallet_id}")

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
