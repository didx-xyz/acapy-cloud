# Verifier

## Verifying end-points

- AnonCreds
  - get exchange record by id ✅
  - get exchange records ✅
  - send proof ✅
  - accept proof ✅
  - reject proof ✅
  - delete proofs ✅
  - get credentials for proof ✅

- JSON-LD/dif_proofs
  - no tests

## Proof revoked

Find test file [here](/app/tests/e2e/verifier/test_proof_revoked_credential.py)

`app/tests/e2e/verifier/test_proof_revoked_credential.py`

### test_proof_revoked_credential_anoncreds (Skipped in regression run)

Acme send proof to Alice, with `non_revoked` interval and restriction on `cred_def`, Alice accepts proof.
Wait for `state: done` and assert proof fails with `verified: false`

### test_regression_proof_revoked_anoncreds_credential

Acme send proof request to Alice, with `non_revoked` interval and restriction on regression `cred_def`, Alice accepts proof.
Wait for `state: done` and assert proof fails with `verified: false`

## Get proof test

Find test file [here](/app/tests/e2e/verifier/anoncreds/test_get_credentials_by_proof_id.py)

`app/tests/e2e/verifier/anoncreds/test_get_credentials_by_proof_id.py`

### test_limit_and_offset (Skipped in regression run)

Issue credentials to Alice with fixture.

Acme sends proof to Alice, Alice waits for `state: request-received`.

Alice matches proof to credentials with `limit` and `offset` params.

Assert expected length on response.

## Get records paginated

Find test file [here](/app/tests/e2e/verifier/anoncreds/test_get_records_paginated.py)

`app/tests/e2e/verifier/anoncreds/test_get_records_paginated.py`

### test_get_presentation_exchange_records_paginated (Skipped in regression run)

Acme sends 5 proof requests to Alice with restriction on `cred_def`.

Alice gets proof records with `limit`, `offset`, `descending` and `state` query params.

Assert length and order is correct depending on query params.

## Test many revocations

Find test file [here](/app/tests/e2e/verifier/anoncreds/test_many_revocations.py)

`app/tests/e2e/verifier/anoncreds/test_many_revocations.py`

### test_revoke_many_credentials

Fixture issues many (75) credentials to Alice and revokes them `auto_publish: true`.

Acme sends proof with restriction on `cred_def`. Alice responds wait for `state:done`.

Asserts assert proof fails with `verified: false`.

## Predicate proofs

Find test file [here](/app/tests/e2e/verifier/anoncreds/test_predicate_proofs.py)

`app/tests/e2e/verifier/anoncreds/test_predicate_proofs_anoncreds.py`

### test_predicate_proofs_anoncreds

Acme send predicate proof on credential attribute `age` with `p_value: 18`.

Expecting `verified: true` for `">", ">="` and failures when `"<", "<="` since Alice `age` over 18.

## Self attested

Find test file [here](/app/tests/e2e/verifier/anoncreds/test_self_attested.py)

`app/tests/e2e/verifier/anoncreds/test_self_attested_anoncreds.py`

### test_self_attested_attributes_anoncreds

Acme sends proof request to Alice with `self_attested` field. Alice responds with value for self attested field.

Notes: Verifier must request attr for proof to be sent.
Question: can alice ever just respond with a self_attested attr?

## Proofs via OOB

Find test file [here](/app/tests/e2e/verifier/anoncreds/test_verifier_oob.py)

### test_accept_proof_request_oob

Bob creates proof request (Bob not a verifier) sends it via OOB attachment.

ALice accepts OOB and responds to proof.

Proof runs to `state: done`

### test_accept_proof_request_verifier_oob_connection (Skipped in regression run)

Alice accepts Acme's TR OOB invitation. Acme uses that connection to send proof to Alice.

Proof runs till `state:done` and assert `verified`

### test_saving_of_presentation_exchange_records

Test parametrized `save_exchange_record: [None, False, True]` for both Alice and Acme.

Proof is run to `done` state.

If `save_exchange_record: None/False` assert tenant cant get exchange record, if `true` assert tenant can get exchange record.

## Verifier tests

Find test file [here](/app/tests/e2e/verifier/anoncreds/test_verifier.py)

### test_send_anoncreds_proof_request

Acme sends proof to Alice. ALice waits for `state: request-received`.

Acme deletes proof (Clean-up)

### test_accept_anoncreds_proof_request

Acme send proof to Alice.

Proof runs to `state:done`, assert proof is `verified: true`.

### test_reject_anoncreds_proof_request

Parametrized with `"delete_proof_record", [True, False]`.

Acme sends proof to Alice, Alice receives request and rejects the proof.

Wait for state for `state: abandoned`.

If `delete_proof_record: True` wait for state deleted.

### test_get_proof_and_get_proofs_anoncreds

Acme sends 2 proofs to Alice.

Alice responds to one of the proofs. Acme gets proofs with query params:

- state
- role
- connection_id
- thread_id
- And a combination of all the params

### test_delete_anoncreds_proof

Acme sends proof to Alice.

Acme deletes proof by id and asserts `204` response code.

### test_get_anoncreds_credentials_for_request

Acme sends proof to Alice.

Alice matches proof to credentials, assert credentials in response with expected fields.

### test_accept_anoncreds_proof_request_verifier_has_issuer_role

Meld_co (both issuer and verifier roles) sends proof to Alice.

Assert proof runs to done.

### test_saving_of_anoncreds_presentation_exchange_records

Test parametrized `save_exchange_record: [None, False, True]` for both Alice and Acme.

Proof is run to `done` state.

If `save_exchange_record: None/False` assert tenant cant get exchange record, if `true` assert can get exchange record.

### test_restrictions_on_attr

Test parametrized with `"value", ["44", "99"]`

Acme sends Alice a proof request with restriction `"attr::age::value": value`.

This enforces that the credential used to respond to proof has a attribute `age` with `value`.

Assert credential returned from matching proof with credential has attribute `age == value`.
