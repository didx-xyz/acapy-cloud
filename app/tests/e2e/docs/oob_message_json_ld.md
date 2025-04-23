# OOB/JSON_LD/MESSAGE

The JSON_LD sign and verify end-points are deprecated, should we drop support them?

## JSON_LD sign and verify endpoints

- AnonCreds
  - Sign &#x2611;
  - Verify &#x2611;

## Json_LD sign/verify end-points

Find test file [here](/app/tests/e2e/test_jsonld.py)

`app/tests/e2e/test_jsonld.py`

### test_sign_jsonld

First: assert `422` if both `pub_did` and `verkey` passed in sign payload.

Second: Sign `json_ld` credential with Faber `pub_did` and assert response contains expected fields.

Third: Sign `json_ld` credential with Faber `verkey` of `pub_did` and assert response contains expected fields.

Lastly: Sign `json_ld` credential with no `verkey` or `pub_did` and assert response contains expected fields.
(Should this be possible...)

### test_verify_jsonld

First: assert `400` if both `pub_did` and `verkey` passed in verify payload.

Second: assert `422` if try to verify with wrong did.

Third: assert `204` when verifying with verkey.

## Messaging end-points

- send trust ping &#x2611;
- send message &#x2612;
  - never check if bob receives message

## Messaging tests

Find test file [here](/app/tests/e2e/test_messaging.py)

`app/tests/e2e/test_messaging.py`

### test_send_trust_ping

Alice sends Bob a trust ping over their connection.

Asserts `200` response code and `thread_id` in response.

### test_send_message

Alice sends Bob a message. Assert `200` response.

We should check if Bob gets message.

I think we need to connect the wires for these messages.

## OOB end-points

- AnonCreds
  - Create invitation &#x2611;
  - Accept invitation &#x2611;
  - Connect via pud_did &#x2611;

## OOB tests

Find test file [here](/app/tests/e2e/test_oob.py)

### test_create_invitation_oob

Bob creates OOB invitation (`create_connection:true`), assert `200` response code.

Also asserts some expected fields, and does some regex matching on the `invitation_url`.

### test_accept_invitation_oob

Bob creates OOB invitation.

Alice accepts the invitation, with invitation field from create response.

Alice waits for `state: completed` for connection. Alice gets created connection record by id, asserts field in response.

### test_oob_connect_via_public_did

Bob calls `connect-public-did` with Faber's public did. Bob waits for `state: request-sent`,
asserts `their_public_did` is Faber's in events body.
