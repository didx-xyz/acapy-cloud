# Tenants

## Tenants end-points

- create tenant ✅
- get access-token ✅
- update tenant ✅
- get tenant by id ✅
- get tenants ✅
- delete tenant ✅

## Tenant test

Find test file [here](/app/tests/e2e/test_tenants.py)

`app/tests/e2e/test_tenants.py`

### test_post_wallet_auth_token (Skipped in regression run)

Tenant-admin role creates tenant.

Tenant-admin role tries to get `token` of bad wallet id and asserts `404`.

Tenant-admin role then tries to get `token` with created tenant's `wallet_id` but bad `group_id` and assert `404`.

Tenant-admin then gets `token` with created tenant wallet_id and group_id, asserts `200` response and that token in response.

### test_create_tenant_member_wo_wallet_name (Skipped in regression run)

Tenant-admin role creates tenant without a `wallet_name`.

Use created tenant's wallet id to get tenant from agent and assert response,
from create tenant, is the equal to response from agent.

### test_create_tenant_member_w_wallet_name (Skipped in regression run)

Tenant-admin role creates tenant with a `wallet_name`.

Use created tenant's `wallet_id` to get tenant from agent and
assert response, from create tenant, is the equal to response from agent.

Tenant-admin then tries to create tenant with same `wallet_name` and asserts `409`.

### test_create_tenant_issuer (Skipped in regression run)

Tenant-admin creates tenant with `issuer` role.

Asserts tenant on TR by getting actor from TR with `wallet_id`.

Using the `public_did` of endorser, get connection of tenant to endorser and assert it's state is active.

Assert actor from TR has same values as created tenant.

Assert `409` when trying to create tenant with same label name. (Can't have same label name on TR)

### test_create_tenant_verifier (Skipped in regression run)

Tenant-admin creates tenant with `verifier` role.

Asserts tenant on TR by getting actor from TR with `wallet_id`.

Assert TR invitation is in verifier's connections. Assert actor on TR has same name, did and role as created tenant.

### test_update_tenant_verifier_to_issuer (Skipped in regression run)

Tenant-admin creates tenant with `verifier` role. Again assert tenant on TR with correct TR invitation and values.

Assert update call will fail if bad `wallet_id` or `group_id` is used.

Call update tenant with new `wallet_label`, `image_url` and `roles` (`["issuer", "verifier"]`).

Assert update response contains expected fields. Assert updated tenant has connection with endorser, and connection is active.

And actor on TR has been updated and has new fields.

### test_get_tenants (Skipped in regression run)

Tenant-admin creates tenant. uses created tenant's `wallet_id` to get tenant by id.

Assert gotten tenant and created tenant are equal.

Tenant-admin creates one more tenant. Tenant-admin then calls get all tenants for `group_id`.

Asserts created tenants are in the response and all have the same `group_id`.

### test_get_tenants_by_group (Skipped in regression run)

Tenant-admin creates tenant with `group_id`. Then calls get tenants with `group_id`.

Assert response has at least one tenant and contains created tenant.

Then call get tenants with bad group_id and assert response is empty list.

### test_get_tenants_by_wallet_name (Skipped in regression run)

Tenant-admin creates tenant. Calls get tenants with `wallet_name` as query param.

Asserts response only contains one tenant and is created tenant.

Call get tenants with un-used name as query param and asserts empty response.

Then calls get tenants with `wallet_name` as query param but wrong `group_id`, asserts empty response.

### test_get_tenant (Skipped in regression run)

Tenant-admin creates tenant. Calls get tenant with bad `wallet_id` and asserts `404` response.

Calls get tenant with created `wallet_id` but wrong `group_id` and asserts `404`.

Then calls get tenant with created `wallet_id` and correct `group_id`, asserts `200` response and
returned tenant is equal to created tenant.

### test_delete_tenant (Skipped in regression run)

Tenant-admin creates verifier tenant, asserts tenant is on TR by getting by `wallet_id`.

Assert delete endpoint returns `404` if bad `wallet_id`/`group_id` is used.

Then delete verifier tenant and assert `204` response and assert verifier tenant not on TR anymore.

### test_extra_settings (Skipped in regression run)

Tenant-admin creates tenant with `"ACAPY_AUTO_ACCEPT_INVITES": True`.

Call agent directly and assert wallet setting have `auto_accept_invites` as `true`.

Call update tenant with `"ACAPY_AUTO_ACCEPT_INVITES": False` .

Again call agent and assert wallet setting has `auto_accept_invites` as `false`.

Also assert when calling update on tenant with bad extra settings that it raises `422`

### test_create_tenant_validation (Skipped in regression run)

Assert `422` is raise if trying to use unacceptable special chars in `wallet_label`, `wallet_name` and `group_id`.

Also assert `422` if a too long `wallet_name` or `wallet_label` is used.

### test_get_wallets_paginated (Skipped in regression run)

Tenant-admin creates 5 wallets/tenants.

Calls get tenants with `limit`, `offset` and `descending`. Assert order correct depending if on descending true or false.

Assert correct number of tenants in response, depending on limit, and
assert unique response when limiting to `1` response and stepping with offset.
