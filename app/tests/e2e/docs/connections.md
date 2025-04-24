# Connections

## Connections end-points

- Create invitation ✅
- Accept Invitation ✅
- get connections ✅
- get by id ✅
- get connections paginated ✅
- delete connections ✅
- did-exchange create request ✅
- did-exchange accept request ✅
- did-exchange rotate ✅
- did-exchange hang-up ✅
- reject did_exchange request ❌

The `reject did_exchange request` end-point is not tested.

## did exchange test

Find test file [here](/app/tests/e2e/test_did_exchange.py)

`app/tests/e2e/test_did_exchange.py`

### test_create_did_exchange_request

Test parametrization

```text
  "use_did, use_did_method, use_public_did",
    [
        (None, None, False),
        (True, None, False),
        (None, "did:peer:2", False),
        (None, "did:peer:4", False),
        (True, "did:peer:4", False),
        (None, None, True),
    ],
```

Scenarios:

1. connection to public did of issuer.
2. connection to public did of issuer specifying own did to use.
3. connection to public did of issuer use did method: `did:peer:2`
4. connection to public did of issuer use did method: `did:peer:4`
5. Failure both `use_did` and `use_did_method` specified.
6. Failure holder does not have public did but passed `use_public_did: true`

### test_accept_did_exchange_invitation

Change `extra_settings` on faber wallet set `"ACAPY_AUTO_ACCEPT_REQUESTS": False` and explicitly accept `did_exchange` request

## did rotate tests

Find test file [here](/app/tests/e2e/test_did_rotate.py)

`app/tests/e2e/test_did_rotate.py`

### test_rotate_did

Create `did_exchange` connection between faber and alice.

Then rotate the did used for connection.

First test rotate to `did:peer:2`, second test rotate to `did:peer:4`

### test_hangup_did_rotation

Create `did_exchange` connection between Faber and Alice. Alice calls `hang_up` on did used for connection.
Check that connection is deleted for both Alice and Faber.

## Connection test

Find test file [here](/app/tests/e2e/test_connections.py)

`app/tests/e2e/test_connections.py`

### test_get_connections

Create connection between Alice and Bob. Get Alice connections and filter with query params:

- state
- alias
- invitation_key
- invitation_msg_id
- my_did
- their_did
- their_public_did
- their_role

### test_get_connection_by_id

Create connection between alice and Bob and get connection by id.

### test_delete_connection

Create connection and delete, assert 404 when trying to get by id.

### test_get_connections_paginated (Skipped in regression run)

Create 5 connections between Alice and Bob. Get connections with `limit`, `offset` and `descending: true/false`,
assert expected nr of returned connection are in expected order.
