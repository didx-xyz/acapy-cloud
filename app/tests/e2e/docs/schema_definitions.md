# Schema/definitions

## Definitions end-points

Schemas

- AnonCreds
  - create* &#x2611;
  - get schemas &#x2612;
  - get schema by id &#x2611;

There is no test for getting all schemas.

Cred-defs

- AnonCreds
  - Create* &#x2611;
  - get cred_defs &#x2612;
  - get cred_def by id &#x2612;

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
