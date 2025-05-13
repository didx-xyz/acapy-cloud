/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import http from "k6/http";

export function getAuthHeaders() {
  let tenantAdminHeaders, governanceHeaders;

  if (__ENV.USE_ENTERPRISE === 'true') {
    // Only get tokens once for better performance
    const token = getBearerToken();
    const governanceToken = getGovernanceBearerToken();

    tenantAdminHeaders = { 'Authorization': `Bearer ${token}` };
    governanceHeaders = { 'Authorization': `Bearer ${governanceToken}` };
  } else {
    console.log("Using API keys for authentication");
    tenantAdminHeaders = { 'x-api-key': `tenant-admin.${__ENV.TENANT_ADMIN_API_KEY}` };
    governanceHeaders = { 'x-api-key': `governance.${__ENV.GOVERNANCE_API_KEY }` };
  }

  return { tenantAdminHeaders, governanceHeaders };
}

export function getBearerToken() {
  const url = `${__ENV.CLOUDAPI_URL}/${__ENV.OAUTH_ENDPOINT}`;
  const clientId = __ENV.CLIENT_ID;
  const clientSecret = __ENV.CLIENT_SECRET;
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
  const url = `${__ENV.CLOUDAPI_URL}/${__ENV.GOVERNANCE_OAUTH_ENDPOINT}`;
  const clientId = __ENV.GOVERNANCE_CLIENT_ID;
  const clientSecret = __ENV.GOVERNANCE_CLIENT_SECRET;
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
