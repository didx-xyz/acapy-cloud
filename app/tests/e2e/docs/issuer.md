# Issuer

## Issuer end-points

- AnonCreds
  - Create offer ✅
  - Send offer ✅
  - request offer ✅

- Json_ld/dif_proof
  - Create offer ✅
  - Send offer ✅
  - request offer ✅

- All
  - get exchange record by id ✅
  - get exchange records ✅
  - delete (clean-up only) ❌

Saving exchange records and pagination on exchange records are tested.

There are no explicit `delete exchange records` tests for exchange records. Only being called for clean-up.
The offer send via OOB attachment is never accepted by holder for all scenarios (anoncreds/dif_proof)

### test_send_credential

Faber sends credential to Alice, assert expected fields in response, wait for `offer-sent` state.

Faber deletes exchange record.

### test_create_offer

Faber creates credential offer. Assert expected fields in response. Wait for `offer-sent` state.

Faber deletes exchange record.

### test_send_credential_request

Faber sends credential offer to Alice. Alice wait for `offer-received`.

Alice requests credential offer.

Wait for `request-sent` state for Alice and `request-received` state for faber.

## Save exchange record

Find test file [here](/app/tests/e2e/issuer/test_save_exchange_record.py)

`app/tests/e2e/issuer/test_save_exchange_record.py`

### test_issue_credential_with_save_exchange_record

Faber issues credential to Alice wait for `state: done`.

Alice can't get exchange record did not request with `save_exchange_record: true`

If `save_exchange_record: None/false` 404 when Faber tries to get exchange when `state:done`

If `save_exchange_record: true` Faber gets exchange record wit expected exchange id.

### test_request_credential_with_save_exchange_record

Faber issues credential to Alice wait for `state: done`.

Alice requested with param `save_exchange_record`.

If `save_exchange_record: None/false` 404 when Alice tries to get exchange when `state:done`

If `save_exchange_record: true` Alice gets exchange record wit expected exchange id.

### test_get_cred_exchange_records

Faber issues 2 credentials to Alice.

Get exchange records with query params and filter out old exchange records:

- ?state=done
- ?role=issuer
- ?thread_id=...
- ?connection_id=123&thread_id=123&role=asf&state=asd (expect failure)

## Issuer end-points pagination

Find test file [here](/app/tests/e2e/issuer/test_get_records_paginated.py)

`app/tests/e2e/issuer/test_get_records_paginated.py`

### test_get_credential_exchange_records_paginated (Skipped in regression run)

For `anoncreds` credential type:

Faber sends credentials to Alice, Alice never requests credentials.

Faber gets exchange records with `limit`, `offset` and `descending: true/false`,
assert expected length/order of response

## AnonCreds credentials

Find test file [here](/app/tests/e2e/issuer/test_anoncreds_credentials.py)

### test_send_credential_oob (anoncreds)

Faber `creates_offer` and sends offer to Alice via OOB attachment (Create `connection:false`).

Alice accepts OOB invitation, receives credential offer. Then Faber deletes credential exchange record.

>Note: Never accepts offer.

### test_send_credential_and_request

Faber sends credential to Alice.

Wait for state Faber: `offer-sent` and Alice: `offer-received`.

Alice request credential, assert `200` response.

Wait for state Alice: `request-sent` and Faber `request-received`.

### test_revoke_credential (anoncreds)

Faber issues credential to Alice.

Wait for credential issuance `state:done`.

Faber revokes with `auto_publish: true` assert `200` response and assert length of `cred_rev_ids_published` is 1.

## LD_proof ed25519

Find test file [here](/app/tests/e2e/issuer/ld_proof/test_ld_proof_did_key_ed25519.py)

### test_send_jsonld_key_ed25519

Faber send `ld_proof/json_ld` credential, with `ed25519` did, to Alice.

Alice receives offer. Assert expected fields in offer.

Faber deletes exchange record.

### test_send_jsonld_oob

Faber creates connection with Alice with OOB end-point.

Faber sends `ld_proof/json_ld` credential, with `ed25519` signature did, via OOB connection id.

Alice receives offer. Faber Deletes exchange record.

### test_send_jsonld_request and test_issue_jsonld_ed

Faber send `ld_proof/json_ld` credential, with `ed25519` signature did, to Alice.

Alice requests offer, assert `200` response and wait for `sate:done`.

### test_send_jsonld_mismatch_ed_bbs

Faber send `ld_proof/json_ld` credential, with `ed25519` signature did but `"proofType": "BbsBlsSignature2020"`.

Expect failure as did signature type does not match proof type.

## LD_proof did:cheqd

Find test file [here](/app/tests/e2e/issuer/ld_proof/test_ld_proof_did_cheqd.py)

Same as `app/tests/e2e/issuer/ld_proof/test_ld_proof_did_key_ed25519.py` section above just with cheqd did.
