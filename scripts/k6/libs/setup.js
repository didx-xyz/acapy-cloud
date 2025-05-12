import { check } from "k6";
import { createIssuerIfNotExists } from "../libs/issuerUtils.js";
import { createSchemaIfNotExists } from "../libs/schemaUtils.js";
import { setupAuth, setupGovernanceAuth } from "./auth.js";
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
  const bearerToken = setupAuth();
  const governanceBearerToken = setupGovernanceAuth();
  const issuers = [];

  for (let i = 0; i < numIssuers; i++) {
    console.log(`Creating issuer ${issuerPrefix}_${i}`);
    const walletName = `${issuerPrefix}_${i}`;
    // const hack = `${walletName}_0`;

    const issuerData = createIssuerIfNotExists(bearerToken, walletName);
    check(issuerData, {
      "Issuer data retrieved successfully": (data) =>
        data !== null && data !== undefined,
    });

    if (!issuerData) {
      console.error(`Failed to create or retrieve issuer for ${walletName}_0`);
      return issuers;
    }

    const { issuerWalletId, issuerAccessToken } = issuerData;
    const credentialDefinitionId = getCredentialDefinitionId(
      issuerAccessToken,
      credDefTag
    );

    if (credentialDefinitionId) {
      console.log(
        `Credential definition already exists for issuer ${walletName}_0 - Skipping creation`
      );
      issuers.push({
        walletName: walletName,
        walletId: issuerWalletId,
        accessToken: issuerAccessToken,
        credentialDefinitionId,
      });
    } else {
      console.warn(
        `Failed to get credential definition ID for issuer ${walletName}_0`
      );

      const schemaId = createSchemaIfNotExists(
        governanceBearerToken,
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
        console.log(
          `Credential definition created successfully for issuer ${walletName}_0`
        );
        issuers.push({
          walletName: walletName,
          walletId: issuerWalletId,
          accessToken: issuerAccessToken,
          credentialDefinitionId: credentialDefinitionId,
        });
      } else {
        console.error(
          `Failed to create credential definition for issuer ${walletName}_0`
        );
      }
    }
  }

  return issuers;
}
