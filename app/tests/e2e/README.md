# End to end tests scenarios

Below we attempt to indicate which end-points of the api is tested with e2e tests.

End-points not tested:

- Connections
  - reject did_exchange request

- Schemas
  - get schemas (missing for anoncreds)

- Cred_defs
  - get cred-defs
  - get cred-defs by id

- Issuer
  - delete exchange records

- Verifier
  - create request (AnonCreds is tested by Bob??)
  - No proofs for dif_proof/json_ld type

- Wallet
  - get MIME type
  - get revocation status
  - get all w3c credentials
  - get w3c credentials by id
  - delete w3c credential
  - rotate key pair (did)
  
- OOB
  - Where the OOB attachment is tested for issuing the credential is never accepted

- Message
  - send message (never check if bob receives message)

## Connections end-points

- Create invitation ✅
- Accept Invitation ✅
- get connections ✅
- get by id ✅
- delete connections ✅
- did-exchange create request ✅
- did-exchange accept request ✅
- did-exchange rotate ✅
- did-exchange hang-up ✅
- reject did_exchange request ❌

See breakdown of tests [here](/app/tests/e2e/docs/connections.md)

## Definitions end-points

Schemas

- AnonCreds
  - create* ✅
  - get schemas ❌
  - get schema by id ✅

Cred-defs

- AnonCreds
  - Create* ✅
  - get cred_defs ❌
  - get cred_def by id ❌

See breakdown of tests [here](/app/tests/e2e/docs/schema_definitions.md)

## Issuer end-points

- AnonCreds
  - Create offer ✅
  - Send offer ✅
  - Accept offer ✅

- Json_ld/dif_proof
  - Create offer ✅
  - Send offer ✅
  - Accept offer ✅

- All
  - get exchange record by id ✅
  - get exchange records ✅
  - delete (clean-up only) ❌

See breakdown of tests [here](/app/tests/e2e/docs/issuer.md)

## Revocation end-points

- AnonCreds
  - Revoke ✅
  - Clear pending ✅
  - Publish pending ✅
  - Fetch revocation record ✅
  - Get pending ✅
  - Fix rev_reg ✅

See breakdown of tests [here](/app/tests/e2e/docs/revocation.md)

## Verifying end-points

- AnonCreds
  - create-request ✅ (tested by Bob??)
  - get exchange record by id ✅
  - get exchange records ✅
  - send proof ✅
  - accept proof ✅
  - reject proof ✅
  - delete proofs ✅
  - get credentials for proof ✅

- JSON-LD/dif_proofs
  - no tests

See breakdown of tests [here](/app/tests/e2e/docs/verifier.md)

## Tenants end-points

- create tenant ✅
- get access-token ✅
- update tenant ✅
- get tenant by id ✅
- get tenants ✅
- delete tenant ✅

See breakdown of tests [here](/app/tests/e2e/docs/tenant.md)

## Wallet end-points

- Credentials
  - get credentials ✅
  - get credential by id ✅
  - delete credentials ✅
  - get credentials with limit ✅
  - get MIME type ❌
  - get revocation status ❌
  - get all w3c credentials ❌
  - get w3c credentials by id ❌
  - delete w3c credential ❌

- DIDs
  - List dids ✅
  - create local did ✅
  - get pub did ✅
  - get did endpoint ✅
  - set pub did ✅
  - set did endpoint* ✅
  - rotate key pair ❌

- JWT
  - Sign ✅
  - verify ✅

- SD-JWT
  - Sign ✅
  - verify ✅

See breakdown of tests [here](/app/tests/e2e/docs/wallet.md)

## JSON_LD endpoints

- Sign ✅
  - Note: failures are ignored, because json-ld.org is sometimes unresolvable, leading to 500 error in ACA-Py
- Verify ✅

See breakdown of tests [here](/app/tests/e2e/docs/oob_message_json_ld.md)

## OOB end-points

- Create invitation ✅
- Accept invitation ✅
- Connect via pud_did ✅

See breakdown of tests [here](/app/tests/e2e/docs/oob_message_json_ld.md)

`*` These end-points' tests are not calling the api directly but import the functions into the pytest environment
and executing them there.

## Miscellaneous tests

These test cover some e2e auth tests, some error handling and some tests on un-expected failures with some models.

See breakdown of tests [here](/app/tests/e2e/docs/miscellaneous.md)
