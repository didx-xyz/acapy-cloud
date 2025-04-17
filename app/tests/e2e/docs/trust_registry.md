# TR

## Trust registry test

Find test file [here](/app/tests/e2e/test_trust_registry.py)

`app/tests/e2e/test_trust_registry.py`

### test_get_schemas

Call get schemas, assert `200` response and assert length of response is greater than 2.

### test_get_schema_by_id

Call get schema id, with id of fixture `schema_id`, assert `200` response and have expected fields.

Also assert a `404` when calling get schema with bad id.

### test_get_actors

Call get all actors, assert `200` response and assert actor structure is correct.

Call get all actors with `actor_id` query param. Assert `200` and assert actor the same as
actor gotten from agent. Also call get actors with `actor_did` and `actor_name` and assert the same.

### test_get_actors_x

Assert `404` when calling get actors, with `id`, `name` and `did` that does not exits, with
query params `actor_id`, `actor_did` and `actor_name`.

And assert `400` response when using more than one query param at a time.

### test_get_issuers

Call get issuers and assert `200` response.

### test_get_verifiers

Call get verifiers and assert `200` response
