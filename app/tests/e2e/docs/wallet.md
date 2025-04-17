# Wallet

## Wallet credentials end-points

- Credentials
  - get credentials &#x2611;
  - get credential by id &#x2611;
  - delete credentials &#x2611;
  - get credentials with limit &#x2611;
  - get MIME type &#x2612;
  - get revocation status &#x2612;
  - get all w3c credentials &#x2612;
  - get w3c credentials by id &#x2612;
  - delete w3c credential &#x2612;

## Credential test

Find test file [here](/app/tests/e2e/test_wallet_credentials.py)

`app/tests/e2e/test_wallet_credentials.py`

### test_get_credentials

Alice calls get credentials and asserts `200` response.

### test_get_and_delete_credential_record (Skipped in regression run)

Alice gets all credentials. Get `credential_id` of first credential in the list and call get credential by id.

Then Alice deletes that credential and assert `204` status code.

Alice gets all credentials again and assert deleted credential is not in that list

### test_get_credential_record_with_limit (Skipped in regression run)

Alice calls get credentials with pagination params and assert expected response lengths.
Also assert `422` response if invalid params are used.

- DIDs
  - List dids &#x2611;
  - create local did &#x2611;
  - get pub did &#x2611;
  - get did endpoint &#x2611;
  - set pub did &#x2611;
  - set did endpoint* &#x2611;

`*` api endpoint not called
No test for rotate key pair

## Did test

Find test file [here](/app/tests/e2e/test_wallet_dids.py)

`app/tests/e2e/test_wallet_dids.py`

### test_list_dids

First get the initial set of dids for governance role.

Governance then calls list dids.

Then assert dids are initial dids.

### test_create_local_did

Governance calls create did. We assert `200` response code.

Assert the response contains `did` and `verkey` field.

### test_get_public_did

Governance role calls get public did. We assert `200` response code.

Assert the response contains `did` and `verkey` field.

Call get public did function directly assert the responses are the same.

### test_get_did_endpoint

Governance calls create did. Governance gets endpoint for created did.

Assert `200` response code and assert created did in response.

### test_set_public_did (Skipped in regression run)

Governance creates did. Post did to ledger with verkey.

Governance calls set public did with created did.

Governance calls get public did and assert `200` response and created did is did in response get public did

### test_set_did_endpoint (Skipped in regression run)

Governance creates did.

Governance sets endpoint of created did to new endpoint.

Governance call get did endpoint on created did and assert it is new endpoint.

- JWS
  - Sign &#x2611;
  - verify &#x2611;

## JWS test

Find test file [here](/app/tests/e2e/test_wallet_jws.py)

`app/tests/e2e/test_wallet_jws.py`

### test_sign_jws_success

Alice creates did (`key`) and uses it to sign simple JWS payload.

Assert `200` response.

### test_sign_jws_x

Assert at least `did` or `verification_method` needed for `JWSCreateRequest`.

Assert `422` when trying to sign empty payload. Assert `422` if bad `did`/`verification_method` used to sign payload.

### test_sign_and_verify_jws_success

Alice creates did to sign jws payload.

Alice signs simple payload and assert `200` response.

Alice calls verify on response, asserts `200` response and `valid` field is `true`

### test_verify_jws_x

Assert `422` response code when trying to verify bad payload.

- SD-JWT
  - Sign &#x2611;
  - verify &#x2611;

## SD-JWS test

Find test file [here](/app/tests/e2e/test_wallet_sd_jws.py)

`app/tests/e2e/test_wallet_sd_jws.py`

### test_sign_sdjws_success

Alice creates did (`key`) and uses it to sign simple JWS payload.

Assert `200` response and `sd_jws` in response.

### test_sign_sdjws_x

Assert at least `did` or `verification_method` needed for `SDJWSCreateRequest`.

Assert `422` when trying to sign empty payload. Assert `422` if bad `did`/`verification_method` used to sign payload.

### test_sign_and_verify_sdjws_success

Alice creates did to sign sd_jws payload.

Alice signs simple payload and assert `200` response.

Alice calls verify on response, asserts `200` response and `valid` field is `true`

### test_verify_sdjws_x

Assert `422` response code when trying to verify bad payload.
