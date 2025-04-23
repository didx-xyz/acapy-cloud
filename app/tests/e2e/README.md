# End to end tests scenarios

Below we attempt to indicate which end-points of the api is tested with e2e tests.

End-points not tested:

- Connections
  - reject did_exchange request

- Schemas
  - get schemas (missing for anoncreds)
  - get schemas by id (missing for indy)

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

- Create invitation &#x2611;
- Accept Invitation &#x2611;
- get connections &#x2611;
- get by id &#x2611;
- delete connections &#x2611;
- did-exchange create request &#x2611;
- did-exchange accept request &#x2611;
- did-exchange rotate &#x2611;
- did-exchange hang-up &#x2611;
- reject did_exchange request &#x2612;

See breakdown of tests [here](/app/tests/e2e/docs/connections.md)

## Definitions end-points

Schemas

- AnonCreds
  - create* &#x2611;
  - get schemas &#x2612;
  - get schema by id &#x2611;

- Indy
  - create* &#x2611;
  - get schema* &#x2611;
  - get schema by id &#x2612;

Cred-defs

- AnonCreds
  - Create* &#x2611;
  - get cred_defs &#x2612;
  - get cred_def by id &#x2612;

- Indy
  - Create* &#x2611;
  - get cred_defs &#x2612;
  - get cred_def by id &#x2612;

See breakdown of tests [here](/app/tests/e2e/docs/schema_definitions.md)

## Issuer end-points

- Indy
  - Create offer &#x2611;
  - Send offer &#x2611;
  - Accept offer &#x2611;

- AnonCreds
  - Create offer &#x2611;
  - Send offer &#x2611;
  - Accept offer &#x2611;

- Json_ld/dif_proof
  - Create offer &#x2611;
  - Send offer &#x2611;
  - Accept offer &#x2611;

- All
  - get exchange record by id &#x2611;
  - get exchange records &#x2611;
  - delete (clean-up only) &#x2612;

See breakdown of tests [here](/app/tests/e2e/docs/issuer.md)

## Revocation end-points

- Indy
  - Revoke &#x2611;
  - Clear pending &#x2611;
  - publish pending revocations &#x2611;
  - Fetch revocation record &#x2611;
  - Get pending revocations &#x2611;
  - Fix rev_reg &#x2611;

- AnonCreds
  - Revoke &#x2611;
  - Clear pending &#x2611;
  - Publish pending &#x2611;
  - Fetch revocation record &#x2611;
  - Get pending &#x2611;
  - Fix rev_reg &#x2611;

See breakdown of tests [here](/app/tests/e2e/docs/revocation.md)

## Verifying end-points

- Indy
  - create-request &#x2612;
  - get exchange record by id &#x2611;
  - get exchange records &#x2611;
  - send proof &#x2611;
  - accept proof &#x2611;
  - reject proof &#x2611;
  - delete proofs &#x2611;
  - get credentials for proof &#x2611;

- AnonCreds
  - create-request &#x2611; (tested by Bob??)
  - get exchange record by id &#x2611;
  - get exchange records &#x2611;
  - send proof &#x2611;
  - accept proof &#x2611;
  - reject proof &#x2611;
  - delete proofs &#x2611;
  - get credentials for proof &#x2611;

- JSON-LD/dif_proofs
  - no tests

See breakdown of tests [here](/app/tests/e2e/docs/verifier.md)

## Tenants end-points

- create tenant &#x2611;
- get access-token &#x2611;
- update tenant &#x2611;
- get tenant by id &#x2611;
- get tenants &#x2611;
- delete tenant &#x2611;

See breakdown of tests [here](/app/tests/e2e/docs/tenant.md)

## Wallet end-points

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

- DIDs
  - List dids &#x2611;
  - create local did &#x2611;
  - get pub did &#x2611;
  - get did endpoint &#x2611;
  - set pub did &#x2611;
  - set did endpoint* &#x2611;
  - rotate key pair &#x2612;

- JWT
  - Sign &#x2611;
  - verify &#x2611;

- SD-JWT
  - Sign &#x2611;
  - verify &#x2611;

See breakdown of tests [here](/app/tests/e2e/docs/wallet.md)

## JSON_LD endpoints

- Sign &#x2611;
  - Note: failures are ignored, because json-ld.org is sometimes unresolvable, leading to 500 error in ACA-Py
- Verify &#x2611;

See breakdown of tests [here](/app/tests/e2e/docs/oob_message_json_ld.md)

## OOB end-points

- Create invitation &#x2611;
- Accept invitation &#x2611;
- Connect via pud_did &#x2611;

See breakdown of tests [here](/app/tests/e2e/docs/oob_message_json_ld.md)

`*` These end-points' tests are not calling the api directly but import the functions into the pytest environment
and executing them there.

## Miscellaneous tests

These test cover some e2e auth tests, some error handling and some tests on un-expected failures with some models.

See breakdown of tests [here](/app/tests/e2e/docs/miscellaneous.md)
