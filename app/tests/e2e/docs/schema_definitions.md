# Schema/definitions

## Definitions end-points

Schemas

- AnonCreds
  - create* ✅
  - get schemas ❌
  - get schema by id ✅

There is no test for getting all schemas.

Cred-defs

- AnonCreds
  - Create* ✅
  - get cred_defs ❌
  - get cred_def by id ❌

`*` These tests are not calling the api directly but import the functions into the pytest environment and executing them
there.

## Schema and Cred_def

Find test file [here](/app/tests/e2e/test_definitions.py)

`app/tests/e2e/test_definitions.py`

### test_create_anoncreds_schema

Faber_anoncreds creates AnonCreds schema, assert expected fields on returned schema.

### test_get_anoncreds_schema

Faber_anoncreds creates AnonCreds schema. Assert Faber_anoncreds,

### test_create_anoncreds_credential_definition

Faber_anoncreds creates `cred_def`.

Assert returned cred_def_id is in expected format.

If support revocation true, assert revocation registries are created with expected fields.
