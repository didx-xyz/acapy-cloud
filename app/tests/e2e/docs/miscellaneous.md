# Miscellaneous

Any tests that don't tests api end-points directly but cover some specific scenarios are noted here.

## Exception handling

Find test file [here](../test_exception_handler.py)

`app/tests/e2e/test_exception_handler.py`

### test_error_handler

With `RichAsyncClient` try to get connections, with `raise_status_error` set to `false`.

Assert `403` response code and response text `{"detail":"Not authenticated"}`

## Proof request models

Find test file [here](../test_proof_request_models.py)

`app/tests/e2e/test_proof_request_models.py`

### test_proof_model_failures

Test parametrized with:

```text
"name, version",
    [
        ("Proof", None),
        (None, "1.0"),
        (None, None),
    ]
```

Acme sends proof request to Alice, without `name` or `version` fields filled.

Assert that when Alice accepts proof it raise `422` error.

Verifier can send proof without `name` `version` fields but will fail when Alice responds to
the proof, bc the fields are not filled.

## Auth tests

Find test file [here](../test_auth.py)

`app/tests/e2e/test_auth.py`

### test_invalid_acapy_auth_header (Skipped in regression run)

Get Alice's `Authorization` token split it on the space and take the second part and use that as token.

Then assert `401` response on calls and assert invalid header structure.

### test_jwt_invalid_token_error (Skipped in regression run)

Create tenant and get its auth token.

Corrupt the token and use the corrupted token in the tenant client.

Attempt to call an endpoint that needs auth and assert `401` response.

### test_invalid_token_error_after_rotation (Skipped in regression run)

Create tenant and create `tenant_client` from `RichAsyncClient` class.

Use token from create in `tenant_client`.

Roll the token of tenant twice and assert `200` response.

Attempt to use `tenant_client` with old token and assert `401` response, token invalid.
