import { check } from "k6";
import { createIssuerIfNotExists } from "../libs/issuerUtils.js";
import { createSchemaIfNotExists } from "../libs/schemaUtils.js";
import { getAuthHeaders } from "./auth.js";
import { log } from "./k6Functions.js";
import {
  createCredentialDefinition,
  getCredentialDefinitionId,
} from "./functions.js";

export function bootstrapIssuer(
  numIssuers,
  issuerPrefix,
  credDefTag,
  schemaName,
  schemaVersion
) {
  const { tenantAdminHeaders, governanceHeaders } = getAuthHeaders();
  const issuers = [];

  for (let i = 0; i < numIssuers; i++) {
    log.debug(`Creating issuer ${issuerPrefix}_${i}`);
    const walletName = `${issuerPrefix}_${i}`;
    // const hack = `${walletName}_0`;

    const issuerData = createIssuerIfNotExists(tenantAdminHeaders, walletName);
    check(issuerData, {
      "Issuer data retrieved successfully": (data) =>
        data !== null && data !== undefined,
    });

    if (!issuerData) {
      log.error(`Failed to create or retrieve issuer for ${walletName}_0`);
      return issuers;
    }

    const { issuerWalletId, issuerAccessToken } = issuerData;
    const credentialDefinitionId = getCredentialDefinitionId(
      issuerAccessToken,
      credDefTag,
      schemaVersion
    );

    if (credentialDefinitionId) {
      log.info(`Credential definition already exists for issuer ${walletName}_0 - Skipping creation`)
      issuers.push({
        wallet_name: walletName,
        wallet_id: issuerWalletId,
        access_token: issuerAccessToken,
        credential_definition_id: credentialDefinitionId,
      });
    } else {
      log.info(`Credential definition not found for issuer ${walletName}_0 - Creating new one`);

      const schemaId = createSchemaIfNotExists(
        governanceHeaders,
        schemaName,
        schemaVersion
      );
      check(schemaId, {
        "Schema ID is not null": (id) => id !== null && id !== undefined,
      });

      const createCredentialDefinitionResponse = createCredentialDefinition(
        issuerAccessToken,
        credDefTag,
        schemaId
      );

      check(createCredentialDefinitionResponse, {
        "Credential definition created successfully": (r) => r.status === 200,
      });

      if (createCredentialDefinitionResponse.status === 200) {
        const { id: credentialDefinitionId } = JSON.parse(
          createCredentialDefinitionResponse.body
        );
        log.info(`definition created successfully for issuer ${walletName}_0`);
        issuers.push({
          wallet_name: walletName,
          wallet_id: issuerWalletId,
          access_token: issuerAccessToken,
          credential_definition_id: credentialDefinitionId,
        });
      } else {
        log.error(`Failed to create credential definition for issuer ${walletName}_0`);
      }
    }
  }

  return issuers;
}
