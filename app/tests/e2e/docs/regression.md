# Regression

## Regression specific tests

`app/tests/e2e/verifier/test_proof_revoked_credential.py`

Find test file [here](/app/tests/e2e/verifier/test_proof_revoked_credential.py)

- test_regression_proof_revoked_indy_credential
- test_regression_proof_revoked_anoncreds_credential
  - Use regression fixtures to issue and revoke alice credentials.
    Then Acme sends Alice a proof restricted to fixture's `cred_def`.
    Alice accepts and proof runs to `state: done`. Assert verified `false`

---

`app/tests/e2e/verifier/anoncreds/test_verifier.py`
`app/tests/e2e/verifier/indy/test_verifier.py`

Find test file [here (anoncreds)](/app/tests/e2e/verifier/anoncreds/test_verifier.py) and [here (indy)](/app/tests/e2e/verifier/indy/test_verifier.py)

- test_regression_proof_valid_anoncreds_credential & test_regression_proof_valid_indy_credential

  Get or issue Alice a valid credential.
  Acme sends proof to Alice with restriction on fixture's`cred_def` with `non_revoked` interval.

  Alice accepts and proof runs to `state: done` and assert `verified` is `true`.
