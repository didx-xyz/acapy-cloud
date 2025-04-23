# Revocation

## Revocation end-points

- Revoke &#x2611;
- Clear pending &#x2611;
- publish pending revocations &#x2611;
- Fetch revocation record &#x2611;
- Get pending revocations &#x2611;
- Fix rev_reg &#x2611;

## Revocation test

Find test file [here](/app/tests/e2e/test_revocation.py)

`app/tests/e2e/test_revocation.py`

### test_clear_pending_revokes_indy/anoncreds (Skipped in regression run)

For anoncreds case just asserts that the endpoint responds with `501` i.e. not implemented for `askar-anoncreds` wallet type.

For Indy clear a specific pending `cred_rev_id` form it `rev_reg`'s pending list.

Assert it state is still `issued` and assert you can't clear it from the list again.

Not clear all for a `rev_reg_id`

### test_clear_pending_revokes_no_map_indy (Skipped in regression run)

Clear all pending revocations with empty payload.

Assert that credential that were pending revocation is still in `state: issued`

### test_clear_pending_revokes_bad_payload_indy/anoncreds (Skipped in regression run)

Try to clear pending revocations with badly formatted payloads, assert pydantic model raises `422`.

In last case only Indy raises `404` as `rev_reg_id` that is used, does not exist and its not implemented for anoncreds.

### test_publish_all_revocations_for_rev_reg_id_indy/anoncreds (Skipped in regression run)

Faber calls publish pending with `rev_rec_id: []` and asserts that all credentials' state,
that were pending for `rev_reg`, has changed to `revoked`

### test_publish_all_revocations_no_payload_indy/anoncreds (Skipped in regression run)

Faber calls publish pending with empty payload i.e. `"revocation_registry_credential_map": {}`

Then asserts that all credentials' state, that were pending for the fixture, has changed to `revoked`

### test_publish_one_revocation_indy/anoncreds (Skipped in regression run)

Faber calls publish pending with `rev_rec_id: [cred_rev_id]`

Then asserts that the credential's state, with `cred_rev_id` used in call, has changed to `revoked`

### test_publish_revocations_bad_payload_indy/anoncreds (Skipped in regression run)

Try to publish pending revocations with badly formatted payloads, assert pydantic model raises `422`.

In last case raises `404`, as `rev_reg_id` that is used, does not exist.

### test_get_pending_revocations_indy/anoncreds (Skipped in regression run)

Faber calls get_pending with `rev_reg_id` and assert that there is 3 or more pending revocations after fixture setup.

If Indy: call `clear_pending` and assert there is no more pending

### test_get_pending_revocations_bad_payload_indy/anoncreds (Skipped in regression run)

Call `get_pending` with bad `rev_reg_id`. If Indy: assert `422`.

If AnonCreds: assert `404` (anoncreds does not validate `rev_reg_id`)

### test_fix_rev_reg_bad_id_indy/anoncreds (Skipped in regression run)

Call `fix_rev_reg` with bad ids. Assert `422` for id with bad format and `404` for ids that don't exist.

AnonCreds test skipped bc no validation on `rev_reg_ids` for AnonCreds.
