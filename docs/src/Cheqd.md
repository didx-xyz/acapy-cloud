# Cheqd

The application is backed by the Cheqd verifiable data registry (VDR). This is made possible by the Cheqd plugin
(see plugin folder) and supporting services, namely the `did-resolver`, `driver-did-cheqd`, and `did-registrar`.

Issuers will have public Cheqd DIDs and their DIDDocs can be found on the VDR.

If you have a local stack running, you can find the DIDDoc with the [resolver](http://resolver.cheqd.127.0.0.1.nip.io/1.0/identifiers/)
by adding your issuer's DID to the end of the URL.

See the example DIDDoc from the VDR below:

```json
"didDocument": {
    "@context": [
      "https://www.w3.org/ns/did/v1",
      "https://w3id.org/security/suites/ed25519-2020/v1"
    ],
    "id": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca",
    "controller": [
      "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca"
    ],
    "verificationMethod": [
      {
        "id": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-1",
        "type": "Ed25519VerificationKey2020",
        "controller": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca",
        "publicKeyMultibase": "z6MkiVAKb1ibt5f1XxizgGgAi7VwBPaXviLZXCFvqYXkHtF4"
      }
    ],
    "authentication": [
      "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-1"
    ],
    "assertionMethod": [
      "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-1"
    ],
    "service": [
      {
        "id": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#did-communication",
        "type": "did-communication",
        "serviceEndpoint": "http://multitenant-agent:3020",
        "recipientKeys": [
          "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-1"
        ],
        "priority": 1
      }
    ]
  }
```

## Rotate Cheqd DID Signing Keys

To be able to rotate the keys of a DID, you need access to the wallet that contains the DID's keys
(i.e., you need to authenticate as that tenant).

### Step 1: Generate new keys in the wallet

```bash
curl -X 'POST' \
  'http://multitenant-agent.cloudapi.127.0.0.1.nip.io/wallet/keys' \
  -H 'accept: application/json' \
  -H 'X-API-KEY: adminApiKey' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eED...-sWvyNFM0f9yjLd5GtIBN90' \
  -H 'Content-Type: application/json' \
  -d '{
  "alg": "ed25519",
  "kid": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2"
}'
```

Response:

```json
{
  "kid": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2",
  "multikey": "z6MkufJTjMDWqvpqzRG24gc8tWNzFRK4RAtEoK3MdDxU8GNj"
}
```

### Step 2: Prepare new DIDDoc payload

```json
  "didDocument": {
    "id": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca",
    "controller": [
      "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca"
    ],
    "verificationMethod": [
      {
        "id": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2",
        "type": "Ed25519VerificationKey2020",
        "controller": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca",
        "publicKeyMultibase": "z6MkufJTjMDWqvpqzRG24gc8tWNzFRK4RAtEoK3MdDxU8GNj"
      }
    ],
    "authentication": [
      "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2"
    ],
    "assertionMethod": [
      "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2"
    ],
    "service": [
      {
        "id": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#did-communication",
        "type": "did-communication",
        "serviceEndpoint": "http://multitenant-agent:3020",
        "recipientKeys": [
          "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2"
        ],
        "priority": 1
      }
    ]
  }
```

Note:

- The `@context` field has been removed.
- All instances of `...#key-1` have been replaced with `...#key-2`, the `kid` from the previous step
- The `publicKeyMultibase` has been updated with the new `multikey` from the previous step

### Step 3: Make the update call

```bash
curl -X 'POST' \
  'http://multitenant-agent.cloudapi.127.0.0.1.nip.io/did/cheqd/update' \
  -H 'accept: application/json' \
  -H 'X-API-KEY: adminApiKey' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...qHbu1EDco-sWvyNFM0f9yjLd5GtIBN90' \
  -H 'Content-Type: application/json' \
  -d '{
  "did": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca",
   "didDocument": {
    "id": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca",
    "controller": [
      "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca"
    ],
    "verificationMethod": [
      {
        "id": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2",
        "type": "Ed25519VerificationKey2020",
        "controller": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca",
        "publicKeyMultibase": "z6MkufJTjMDWqvpqzRG24gc8tWNzFRK4RAtEoK3MdDxU8GNj"
      }
    ],
    "authentication": [
      "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2"
    ],
    "assertionMethod": [
      "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2"
    ],
    "service": [
      {
        "id": "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#did-communication",
        "type": "did-communication",
        "serviceEndpoint": "http://multitenant-agent:3020",
        "recipientKeys": [
          "did:cheqd:testnet:248eee31-4e4c-47fe-9bb5-27a23774f9ca#key-2"
        ],
        "priority": 1
      }
    ]
  },
  "options": {
    "network": "testnet"
  }
}'
```

Hooray! 🥳🎉 Well done, the keys for the DID have been rotated.

## Import Cheqd DID

An existing Cheqd DID can be added to a wallet if you have the signing `keys` for that DID.

Let's import the DID from this DIDDoc:

```json
  "didDocument": {
    "@context": [
      "https://www.w3.org/ns/did/v1",
      "https://w3id.org/security/suites/ed25519-2020/v1"
    ],
    "id": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14",
    "controller": [
      "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14"
    ],
    "verificationMethod": [
      {
        "id": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#key-1",
        "type": "Ed25519VerificationKey2020",
        "controller": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14",
        "publicKeyMultibase": "z6MkfH5psDPV8f3xzPpp1QgMRhgSUC84HjU2JwZU2ZgER7dL"
      }
    ],
    "authentication": [
      "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#key-1"
    ],
    "assertionMethod": [
      "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#key-1"
    ],
    "service": [
      {
        "id": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#did-communication",
        "type": "did-communication",
        "serviceEndpoint": "http://governance-agent:3020",
        "recipientKeys": [
          "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#key-1"
        ],
        "priority": 1
      }
    ]
  }
```

### Step 1: Generate keys from seed

```bash
curl -X 'POST' \
  'http://governance-agent.cloudapi.127.0.0.1.nip.io/wallet/keys' \
  -H 'accept: application/json' \
  -H 'X-API-KEY: adminApiKey' \
  -H 'Content-Type: application/json' \
  -d '{
  "alg": "ed25519",
  "kid": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#key-1",
  "seed": "verySecretPaddedWalletSeedPadded"
}'
```

Note: Use the same `kid` as appears in the DIDDoc.

### Step 2: Import DID

```bash
curl -X 'POST' \
  'http://governance-agent.cloudapi.127.0.0.1.nip.io/did/import' \
  -H 'accept: application/json' \
  -H 'X-API-KEY: adminApiKey' \
  -H 'Content-Type: application/json' \
  -d '{
  "did_document": {
    "id": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14",
    "controller": [
      "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14"
    ],
    "verificationMethod": [
      {
        "id": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#key-1",
        "type": "Ed25519VerificationKey2020",
        "controller": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14",
        "publicKeyMultibase": "z6MkfH5psDPV8f3xzPpp1QgMRhgSUC84HjU2JwZU2ZgER7dL"
      }
    ],
    "authentication": [
      "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#key-1"
    ],
    "assertionMethod": [
      "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#key-1"
    ],
    "service": [
      {
        "id": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#did-communication",
        "type": "did-communication",
        "serviceEndpoint": "http://governance-agent:3020",
        "recipientKeys": [
          "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14#key-1"
        ],
        "priority": 1
      }
    ]
  },
  "metadata": {}
}'
```

Response:

```json
{
  "result": {
    "did": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14",
    "verkey": "ppnGy93o7ZVstz7KqiWac8SecrCsrDfcveYCHiDVtqx",
    "posture": "wallet_only",
    "key_type": "ed25519",
    "method": "cheqd",
    "metadata": {}
  }
}
```

### Step 3: Set DID to public

```bash
curl -X 'POST' \
  'http://governance-agent.cloudapi.127.0.0.1.nip.io/wallet/did/public?did=did%3Acheqd%3Atestnet%3Ae1e2681b-df58-4c75-86fb-1470a30e9b14&create_transaction_for_endorser=false' \
  -H 'accept: application/json' \
  -H 'X-API-KEY: adminApiKey' \
  -d ''
```

Response:

```json
{
  "result": {
    "did": "did:cheqd:testnet:e1e2681b-df58-4c75-86fb-1470a30e9b14",
    "verkey": "ppnGy93o7ZVstz7KqiWac8SecrCsrDfcveYCHiDVtqx",
    "posture": "posted",
    "key_type": "ed25519",
    "method": "cheqd",
    "metadata": {
      "posted": true
    }
  }
}
```

Hooray! 🥳🎉 Well done, the DID can now be used.
