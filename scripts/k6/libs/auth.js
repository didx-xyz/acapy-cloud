/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import http from "k6/http";
import { getOrgId, fetchClientSecret, fetchGovernanceSecret } from './auth-support.js';
import { config } from './config.js';


export function getAuthHeaders() {
  let tenantAdminHeaders, governanceHeaders;

  if (config.auth.useEnterprise) {
    // Only get tokens once for better performance
    console.log("Using Bearer token for authentication");

    const token = getBearerToken();
    const governanceToken = getGovernanceBearerToken();

    tenantAdminHeaders = { 'Authorization': `Bearer ${token}` };
    governanceHeaders = { 'Authorization': `Bearer ${governanceToken}` };
  } else {
    console.log("Using API keys for authentication");
    tenantAdminHeaders = { 'x-api-key': `tenant-admin.${config.auth.tenantAdminApiKey}` };
    governanceHeaders = { 'x-api-key': `governance.${config.auth.governanceApiKey}` };
  }

  return { tenantAdminHeaders, governanceHeaders };
}

export function getBearerToken() {
  // Fetch client secret and org ID
  const clientSecret = fetchClientSecret();
  const orgId = getOrgId();

  const url = `${config.api.cloudApiUrl}/auth/realms/${orgId}/protocol/openid-connect/token`;
  const clientId = config.auth.clientId;
  const requestBody = `grant_type=client_credentials&client_id=${clientId}&client_secret=${clientSecret}`;

  const response = http.post(url, requestBody, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });

  if (response.status === 200) {
    const responseData = JSON.parse(response.body);
    const bearerToken = responseData.access_token;
    return bearerToken;
  }
  console.error("Error:", response.status_text);
  console.error("Response body:", response.body);
  console.error("Error description:", response.json().error_description);
  throw new Error("Failed to obtain bearer token");
}

export function getGovernanceBearerToken() {
  const url = `${config.api.cloudApiUrl}/${config.auth.governanceOauthEndpoint}`;
  const clientId = config.auth.governanceClientId;
  const clientSecret = fetchGovernanceSecret();
  const requestBody = `grant_type=client_credentials&client_id=${clientId}&client_secret=${clientSecret}`;

  const response = http.post(url, requestBody, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });

  if (response.status === 200) {
    const responseData = JSON.parse(response.body);
    const bearerToken = responseData.access_token;
    return bearerToken;
  }
  console.error("Error:", response.status_text);
  console.error("Response body:", response.body);
  console.error("Error description:", response.json().error_description);
  throw new Error("Failed to obtain bearer token");
}
