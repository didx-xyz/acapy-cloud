# Common Steps

This document provides a quick overview of the most common steps: creating wallets, issuing credentials,
and verifying credentials. More detailed descriptions of the different steps can be found in the
[Example Flows](./Example%20Flows.md) document.

> **Note:** It is always helpful to inspect the Swagger UIs to understand
> the available endpoints, their expected inputs, and the corresponding outputs.
> If requests fail, check the Swagger UI to ensure you've called the correct
> endpoint with the correct data. The Swagger UIs are accessible, under a vanilla setup, at:
>
> - **Multitenant-Admin** (Managing tenants) -> [http://cloudapi.127.0.0.1.nip.io/tenant-admin/docs](http://cloudapi.127.0.0.1.nip.io/tenant-admin/docs)
> - **Governance** (Acting as governance) -> [http://cloudapi.127.0.0.1.nip.io/governance/docs](http://cloudapi.127.0.0.1.nip.io/governance/docs)
> - **Tenant** (Acting as a tenant) -> [http://cloudapi.127.0.0.1.nip.io/tenant/docs](http://cloudapi.127.0.0.1.nip.io/tenant/docs)
> - **Public** (Interface to read the trust registry) -> [http://cloudapi.127.0.0.1.nip.io/public/docs](http://cloudapi.127.0.0.1.nip.io/public/docs)
>
> If you find any model descriptions unclear in the document below, try checking the Swagger UI documentation
> before opening an issue.

It is also recommended to understand and perhaps set up a webhook listener (refer to our
[Webhooks doc](./Webhooks.md)). This will significantly aid in observing the
activities occurring in the ACA-Py instances in the background.

## Creating Wallets

The admin "wallet" is already configured as it is not a subwallet on a
multi-tenant agent. To create subwallets for tenants, you have to use the tenant
admin role. The permissions and routing to the correct ACA-Py instance are
handled by acapy-cloud under the hood. You need to provide two things:

1. Authorization in the header: `{"x-api-key": "tenant-admin.APIKEY"}`, where
   `tenant-admin` is a fixed term representing the role, and `APIKEY` is the auth
   token you must know and provide.
   _Note: This auth string is separated by a dot, so keep that in there._

2. The wallet payload (body) of the wallet you want to create, e.g.,

   ```json
   {
     "wallet_label": "Demo Issuer",
     "wallet_name": "Faber",
     "roles": ["issuer"],
     "group_id": "API demo",
     "image_url": "https://upload.wikimedia.org/wikipedia/commons/7/70/Example.png"
   }
   ```

Send this to the `/tenant-admin/v1/admin/tenants` endpoint. You can omit the
roles field altogether or pass "issuer" and/or "verifier". All payloads are
documented in Swagger, so if in doubt, consult the
[Multitenant-Admin docs](http://cloudapi.127.0.0.1.nip.io/tenant-admin/docs).

Creating a tenant with roles will update the trust registry by writing an entry
for an `actor`, including wallet details and its associated roles.

If you wish to later update entities roles, you will have to do that again via
the tenants admin API, which will handle interacting with the trust registry
(see also the Swagger for `update tenant`).

## Creating Schemas

To create schemas and effectively write them to the ledger as well as registering
them on the trust registry, use the governance role:

1. Provide the following authentication header:

   ```json
   { "x-api-key": "governance.ADMIN_API_KEY" }
   ```

   Replace the `ADMIN_API_KEY` with the actual API key. Keep the dot and recall
   that `governance` is a keyword known to acapy-cloud as a role. It will
   resolve the correct endpoint and available actions based on the role and
   provided token.

2. Provide the information about the schema, e.g.:

   ```json
   {
     "name": "yourAwesomeSchemaName",
     "version": "1.3.7",
     "attributes": ["skill", "age"]
   }
   ```

   Note that you will need to have a public DID to do so (if your agent lacks
   one, you can use the governance role to create one: see
   [Bootstrapping the Trust Ecosystem](./Bootstrap%20Trust%20Ecosystem.md)).
   Run the request with the header from 1. and the payload from 2. against the
   [Governance URL](http://cloudapi.127.0.0.1.nip.io/governance/docs)
   and endpoint `/v1/definitions/schemas` (POST method). Upon success, the
   created schema will be returned.

## Issuing a Credential

1. Register a schema (see above)
2. Register an issuer (create a wallet passing "issuer" as a role - see above)
3. Issuer creates credential definition
4. Create a connection between the issuer and prospective holder

   A connection can be created using the
   `/v1/connections/did-exchange/create-request` endpoint of the
   [Tenant URL](http://cloudapi.127.0.0.1.nip.io/tenant/docs).
   Here, you will also need to authenticate via the header, e.g., using

   ```json
   { "x-api-key": "tenant.WALLET_TOKEN" }
   ```

   where the `WALLET_TOKEN` is the bearer token you get from the create
   wallet response for a tenant wallet.

   Use the issuer's public DID as the `their_public_did` parameter in the request.

   This will automatically establish a connection between the issuer and the holder, and can
   be verified by checking the connection records (`GET /v1/connections`) for either party.

   Alternatively, an OOB invitation can be used to create a connection.
   Please see [this example docs](./examples/4.%20Create%20Connection%20with%20Issuer.md) for more details.

5. Issue a credential from issuer to prospect holder

   1. Create and send a credential authenticating with the issuer. The credential
      has the form:

   ```json
   {
     "connection_id": "string",
     "schema_id": "string",
     "attributes": {
       "additionalProp1": "string",
       "additionalProp2": "string",
       "additionalProp3": "string"
     }
   }
   ```

   This should correspond to a schema you created previously, and the
   `connection_id` is the ID of the connection you created in the previous step.
   If you're unsure what that ID is, you can always run a GET request against
   the `connections` endpoint to find it.

6. Accept and store the credential in the holder wallet
7. Using the holder (authenticating with the holder auth header), issue a GET
   request against the `/v1/issuer/credentials` endpoint, providing the connection
   ID of the connection established above. _Note: The connection IDs are unique for
   each entity, so the connection between the issuer and the holder is one
   connection with two separate connection IDs - one for the issuer and one for the
   holder._ This will provide you with a credential record that should be in the
   state of being offered. Providing the connection ID again, you can now use the
   holder to store the credential by posting to
   `/v1/issuer/credentials/{credential_exchange_id}/store`
8. (Optional) Get yor credentials from your wallet (`wallet/credentials`) check
   whether the credential is actually stored. You can also check this via waypoint.

## Verifying a Credential

1. Ensure you followed **Issuing a Credential** steps to have a wallet with a
   credential (prover)
2. Register an entity as a verifier (verifier)
   1. In other words, create or update a wallet, passing the role "verifier"
3. Create a connection between 1. prover and 2. verifier the same way as in
   **Issuing a Credential**
4. Create a proof request (`/v1/verifier/create-request`) using the verifier and
   send it to the prover. Consult the Swagger `verifier` endpoints. POST to
   `/v1/verifier/send-request` with a payload of the following form, replacing the
   values accordingly (and ensuring they can be covered by the previously created
   schema and issued credential):

   ```json
   {
     "connection_id": "string",
     "indy_proof_request": {
       "requested_attributes": {
         "additionalProp1": {
           "name": "string",
           "names": ["string"],
           "non_revoked": {},
           "restrictions": []
         }
       },
       "requested_predicates": {
         "additionalProp1": {
           "name": "string",
           "p_type": "<",
           "p_value": 0,
           "non_revoked": {},
           "restrictions": []
         },
         "name": "string",
         "non_revoked": {},
         "version": "string"
       }
     }
   }
   ```

5. Send the proof request.

   1. From the prover, get the proof records using `/v1/verifier/proofs` and
      create a proof request you want to send, just as above (same payload format
      and endpoint).

6. Accept the proof request.

   1. From the verifier, you can now accept (or reject; see
      `/v1/verifier/reject-request` on Swagger for payload) by POSTing to
      `/v1/verifier/send-request`, adjusting the payload to:

   ```json
   {
     "proof_id": "string",
     "indy_presentation_spec": {
       "requested_attributes": {
         "additionalProp1": {
           "cred_id": "string",
           "revealed": true
         }
       },
       "requested_predicates": {
         "additionalProp1": {
           "cred_id": "string",
           "timestamp": 0
         }
       },
       "self_attested_attributes": {
         "additionalProp1": "string",
         "additionalProp2": "string",
         "additionalProp3": "string"
       }
     }
   }
   ```

7. (Optional) Wait for the prover and verifier's webhook, using waypoint, and see that the
   presentation is acknowledged. Alternatively, GET the proof records and check the
   `state` field.

_Note: There are multiple flows to this "dance". For further details, you may want to refer
to the [official Aries-RFC](https://github.com/hyperledger/aries-rfcs/tree/main/features/0037-present-proof)._

If you'd like to delve deeper into more of acapy-cloud's capabilities,
please see the [Example Flows](./Example%20Flows.md) document.
