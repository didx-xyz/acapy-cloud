// issuerUtils.js
import {
  createIssuerTenant,
  getAccessTokenByWalletId,
  getWalletIdByWalletName,
} from "./functions.js";

export function createIssuerIfNotExists(headers, walletName) {
  let issuerWalletId = getWalletIdByWalletName(headers, walletName);
  let issuerAccessToken;

  if (issuerWalletId !== null) {
    // Issuer exists, retrieve the access token
    issuerAccessToken = getAccessTokenByWalletId(headers, issuerWalletId);
    if (typeof issuerAccessToken !== "string") {
      console.error(
        `Failed to retrieve access token for wallet ID ${issuerWalletId}`
      );
      console.error(`Response body: ${issuerAccessToken}`);
      return null;
    }
  } else {
    // Issuer doesn't exist, create a new one
    try {
      const createIssuerTenantResponse = createIssuerTenant(
        headers,
        walletName
      );
      if (createIssuerTenantResponse.status !== 200) {
        throw new Error(
          `Failed to create issuer tenant. Status: ${createIssuerTenantResponse.status}`
        );
      }
      const tenantData = JSON.parse(createIssuerTenantResponse.body);
      issuerWalletId = tenantData.wallet_id;
      issuerAccessToken = tenantData.access_token;
    } catch (error) {
      console.error(`Error creating issuer tenant for ${walletName}:`, error);
      return null;
    }
  }

  return { issuerWalletId, issuerAccessToken };
}
