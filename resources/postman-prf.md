```mermaid
graph TD
 %% Define styles for different actors with improved contrast
 classDef tenantAdmin fill:#99ff99,stroke:#333,stroke-width:2px,color:#000000,font-weight:bold;
 classDef governance fill:#ff9999,stroke:#333,stroke-width:2px,color:#000000,font-weight:bold;
 classDef issuerTenant fill:#9999ff,stroke:#333,stroke-width:2px,color:#000000,font-weight:bold;
 classDef holderTenant fill:#ffff99,stroke:#333,stroke-width:2px,color:#000000,font-weight:bold;
 classDef publicEndpoint fill:#d3d3d3,stroke:#333,stroke-width:2px,color:#000000,font-weight:bold;
 classDef assertion fill:#ffa500,stroke:#333,stroke-width:2px,color:#000000,font-weight:bold;
 %% Define styles for SSE steps
 classDef sseIssuer stroke:#9999ff,stroke-width:4px,color:#1;
 classDef sseHolder stroke:#ffff99,stroke-width:4px,color:#1;
 %% Start and End
 Start[Start]
 End[End]
 %% Tenant Admin actions
 GetIssuerTenant[Get issuer tenant]:::tenantAdmin
 GetIssuerToken[Get issuer access token]:::tenantAdmin
 CreateIssuer[Create issuer/verifier]:::tenantAdmin
 GetHolderTenant[Get holder tenant]:::tenantAdmin
 GetHolderToken[Get holder access token]:::tenantAdmin
 CreateHolder[Create holder]:::tenantAdmin
 DeleteIssuer[Delete issuer/verifier]:::tenantAdmin
 DeleteHolder[Delete holder]:::tenantAdmin
 %% Governance actions
 GetSchema[Get Schema]:::governance
 CreateSchema[Create Schema]:::governance
 %% Public actions
 VerifyIssuerRegistry[Verify issuer/verifier on trust-registry]:::publicEndpoint
 VerifySchemaRegistry[Verify schema on trust-registry]:::publicEndpoint
 %% Issuer Tenant actions
 GetIssuerPublicDid[Get issuer public did]:::issuerTenant
 GetCredDef[Get Cred Def]:::issuerTenant
 CreateCredDef[Create Cred Def]:::issuerTenant
 CreateCredential[Create Credential]:::issuerTenant
 ListCredentials[List credentials]:::holderTenant
 SendProofRequest[Send Proof Request]:::issuerTenant
 GetProof[Get Proof]:::issuerTenant
 RevokeCredential[Revoke Credential]:::issuerTenant
 CheckRevoked[Check Revoked]:::issuerTenant
 GetIssuerConnectionId[Get issuer connection ID]:::issuerTenant
 %% Holder Tenant actions
 CreateDidExchangeRequest[Create DID exchange request]:::holderTenant
 WaitOfferReceived[Wait for SSE offer-received]:::sseHolder
 GetCredentialsID[Get Credentials ID]:::holderTenant
 AcceptCredential[Accept Credential]:::holderTenant
 WaitRequestReceived[Wait for SSE request-received]:::sseHolder
 GetProofID[Get Proof ID]:::holderTenant
 GetReferent[Get Referent]:::holderTenant
 AcceptProofRequest[Accept Proof Request]:::holderTenant
 %% Shared or system actions
 WaitForSseCompleted[Wait for SSE completed]:::sseHolder
 WaitProofDone[Wait for SSE proof done]:::sseIssuer
 WaitForSSERevoked[Wait for SSE revoked]:::sseIssuer
 %% Assertions
 AssertVerifiedTrue>Assert: verified = true]:::assertion
 AssertVerifiedFalse>Assert: verified = false]:::assertion
 %% Flow
 Start --> GetIssuerTenant
 GetIssuerTenant -->|Issuer exists| GetIssuerToken
 GetIssuerTenant -->|Issuer doesn't exist| CreateIssuer --> VerifyIssuerRegistry --> GetHolderTenant
 GetIssuerToken --> GetHolderTenant
 GetHolderTenant -->|Holder exists| GetHolderToken
 GetHolderTenant -->|Holder doesn't exist| CreateHolder --> GetIssuerPublicDid
 GetHolderToken --> GetIssuerPublicDid --> CreateDidExchangeRequest
 CreateDidExchangeRequest --> WaitForSseCompleted --> GetIssuerConnectionId --> GetSchema
 GetSchema -->|Schema exists| VerifySchemaRegistry
 GetSchema -->|Schema doesn't exist| CreateSchema --> VerifySchemaRegistry
 VerifySchemaRegistry --> GetCredDef
 GetCredDef -->|Cred Def exists| CreateCredential
 GetCredDef -->|Cred Def doesn't exist| CreateCredDef --> CreateCredential
 CreateCredential --> WaitOfferReceived --> GetCredentialsID --> AcceptCredential --> ListCredentials
 ListCredentials --> SendProofRequest --> WaitRequestReceived --> GetProofID --> GetReferent --> AcceptProofRequest --> WaitProofDone --> GetProof
 GetProof -->|Is revokedFlag true| AssertVerifiedFalse
 GetProof -->|Is revokedFlag false| AssertVerifiedTrue
 AssertVerifiedTrue --> RevokeCredential --> CheckRevoked -->|Set revokedFlag = true| WaitForSSERevoked --> SendProofRequest
 AssertVerifiedFalse -->|Is deleteTenantFlag true| DeleteIssuer --> DeleteHolder --> End
 AssertVerifiedFalse -->|Is deleteTenantFlag false| End
 %% Legend
 subgraph Legend
 TenantAdmin[Tenant Admin]:::tenantAdmin
 Governance[Governance]:::governance
 IssuerTenant[Issuer Tenant]:::issuerTenant
 HolderTenant[Holder Tenant]:::holderTenant
 PublicEndpoint[Public]:::publicEndpoint
 end
```
