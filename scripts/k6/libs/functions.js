/* global __ENV, __ITER, __VU, console */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import http from "k6/http";
import sse from "k6/x/sse";
import { log } from "../libs/k6Functions.js";
// let customDuration = new Trend('custom_duration', true);

// Helper function to generate a unique, zero-based index for even distribution of operations
export function getWalletIndex(vu, iter, iterationsPerVu) {
  return (vu - 1) * iterationsPerVu + iter;
}

function logError(response, requestBody) {
  console.error(`Response status: ${response.status}`);
  console.error(`Response body: ${response.body}`);
  if (requestBody) {
    console.error(`Request body: ${requestBody}`);
  }
}

export function createTenant(headers, wallet) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant-admin/v1/tenants`;
  const payload = JSON.stringify({
    wallet_label: wallet.wallet_label,
    wallet_name: wallet.wallet_name,
    wallet_type: "askar-anoncreds",
    group_id: "GroupA",
    image_url:
      "https://upload.wikimedia.org/wikipedia/commons/7/70/Example.png",
  });
  const params = {
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  };

  const response = http.post(url, payload, params);
  if (response.status === 200) {
    return response;
  }
  // Request failed
  console.warn(`Request failed for VU: ${__VU}, ITER: ${__ITER}`);
  logError(response, payload);
  throw new Error("Failed to create tenant");
}

export function getWalletIdByWalletName(headers, walletName) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant-admin/v1/tenants?wallet_name=${walletName}`;
  const params = {
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  };

  const response = http.get(url, params);
  if (response.status >= 200 && response.status < 300) {
    // Request was successful
    const responseData = JSON.parse(response.body);
    // Check if the response is an array and take the first item
    if (Array.isArray(responseData) && responseData.length > 0) {
      const firstItem = responseData[0];
      // Safely access wallet_id without optional chaining
      if (firstItem && firstItem.hasOwnProperty("wallet_id")) {
        return firstItem.wallet_id;
      }
    }
    log.warn(`Wallet not found for wallet_name ${walletName}`);
    log.debug(`Response body: ${response.body}`);
    return null;
  }
  logError(response);
  console.warn(`Request failed for wallet_name ${walletName}`);
  return null;
}

export function getTrustRegistryActor(walletName) {
  const url = `${__ENV.CLOUDAPI_URL}/public/v1/trust-registry/actors?actor_name=${walletName}`;
  const params = {
    headers: {
      "Content-Type": "application/json",
    },
  };

  const response = http.get(url);
  // console.log(`Response: ${response}`)
  if (response.status === 200) {
    // Request was successful
    // console.log(`Issuer found for actor_name ${walletName}`);
    return response;
  }
  logError(response);
  console.warn(`Issuer not on Trust Registry: actor_name ${walletName}`);
  return null;
}

export function getAccessTokenByWalletId(headers, walletId) {
  console.log(`Getting access token for wallet ID: ${walletId}`);
  const url = `${__ENV.CLOUDAPI_URL}/tenant-admin/v1/tenants/${walletId}/access-token`;

  const params = {
    headers: {
      ...headers,
    },
  };

  const payload = JSON.stringify({});
  const response = http.post(url, payload, params);

  if (response.status >= 200 && response.status < 300) {
    // Request was successful
    const responseData = JSON.parse(response.body);
    const accessToken = responseData.access_token;
    const end = new Date();
    // customDuration.add(end - start, { step: 'getAccessTokenByWalletId' });
    return accessToken;
  }
  // Request failed
  console.error(`Request failed with status ${response.status}`);
  console.error(`Response body: ${response.body}`);
  // throw new Error(`Failed to get access token: ${response.body}`);
  const end = new Date();
  // customDuration.add(end - start, { step: 'getAccessTokenByWalletId' });
  return null;
}

export function deleteTenant(headers, walletId) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant-admin/v1/tenants/${walletId}`;
  const params = {
    headers: {
      ...headers,
    },
  };

  try {
    const response = http.del(url, null, params);
    const responseBody = response.body;

    if (response.status === 204 || response.status === 200) {
      // Request was successful
      if (responseBody === null || responseBody === "null") {
        console.log(`Wallet ${walletId} deleted successfully.`);
      } else {
        console.error(
          `Failed to delete wallet ${walletId}. Response body: ${responseBody}`
        );
      }
    } else {
      // Request failed
      console.error(`Request failed with status ${response.status}`);
      console.error(`Response body: ${responseBody}`);
    }

    return response;
  } catch (error) {
    // Handle any errors that occurred during the request
    console.error(`Error deleting tenant: ${error.message}`);
    throw error;
  }
}

export function createIssuerTenant(headers, walletName) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant-admin/v1/tenants`;
  const payload = JSON.stringify({
    wallet_label: walletName,
    wallet_name: walletName,
    wallet_type: "askar-anoncreds",
    roles: ["issuer", "verifier"],
    group_id: "GroupA",
    image_url:
      "https://upload.wikimedia.org/wikipedia/commons/7/70/Example.png",
  });
  const params = {
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  };

  // console.log(`Payload: ${payload}`);
  // console.log(`Params: ${JSON.stringify(params, null, 2)}`);
  // console.log(`URL: ${url}`);

  try {
    const response = http.post(url, payload, params);
    if (response.status >= 200 && response.status < 300) {
      return response;
    }
    logError(response);
    console.warn(`Request failed for wallet_name ${walletName}`);
    return null;
  } catch (error) {
    logError(response);
    console.error(`Error creating issuer tenant: ${error.message}`);
    throw error;
  }
}

export function createInvitation(issuerAccessToken) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/oob/create-invitation`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
    },
  };

  try {
    const response = http.post(url, null, params);
    return response;
  } catch (error) {
    console.error(`Error creating invitation: ${error.message}`);
    throw error;
  }
}

export function getIssuerPublicDid(issuerAccessToken) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/wallet/dids/public`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
    }
  };

  return http.get(url, params);
}

export function createDidExchangeRequest(holderAccessToken, issuerPublicDid) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/connections/did-exchange/create-request?their_public_did=${issuerPublicDid}`;
  const params = {
    headers: {
      "x-api-key": holderAccessToken,
    },
  };

  try {
    // console.log(`Request URL: ${url}`);
    const response = http.post(url, null, params);
    // console.log(`Request params: ${JSON.stringify(params, null, 2)}`);
    // console.log(`Holder Access tpoken: ${holderAccessToken}`);
    // console.log(`Response: ${JSON.stringify(response, null, 2)}`);
    return response;
  } catch (error) {
    console.error(`Error creating invitation: ${error.message}`);
    throw error;
  }
}

export function getHolderConnections(holderAccessToken, holderConnectionId) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/connections/${holderConnectionId}`;
  const params = {
    headers: {
      "x-api-key": holderAccessToken,
    },
  };

  try {
    // console.log(`Request URL: ${url}`);
    const response = http.get(url, params);
    // console.log(`Request params: ${JSON.stringify(params, null, 2)}`);
    // console.log(`Response: ${JSON.stringify(response, null, 2)}`);
    return response;
  } catch (error) {
    console.error(`Error getting holder connections: ${error.message}`);
    throw error;
  }
}

export function getIssuerConnectionId(issuerAccessToken, holderDid) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/connections?their_did=${holderDid}`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
    },
  };

  try {
    // console.log(`Request URL: ${url}`);
    const response = http.get(url, params);
    // console.log(`Request params: ${JSON.stringify(params, null, 2)}`);

    // console.log(`VU ${__VU}: Iteration ${__ITER}: getIssuerConnectionId Response: ${JSON.stringify(response, null, 2)}`);
    return response;
  } catch (error) {
    console.error(`Error creating invitation: ${error.message}`);
    throw error;
  }
}

export function acceptInvitation(holderAccessToken, invitationObj) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/oob/accept-invitation`;
  const params = {
    headers: {
      "x-api-key": holderAccessToken,
      "Content-Type": "application/json",
    },
  };

  try {
    // Construct the request body including the invitation object
    const requestBody = {
      alias: "holder <> issuer",
      invitation: invitationObj,
    };

    const response = http.post(url, JSON.stringify(requestBody), params);
    return response;
  } catch (error) {
    console.error(`Error accepting invitation: ${error.message}`);
    throw error;
  }
}

export function createCredential(
  issuerAccessToken,
  credentialDefinitionId,
  issuerConnectionId,
  dateOfIssue = "2021-09-29" // Default value
) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/issuer/credentials`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
    },
  };

  try {
    // Construct the request body including the invitation object
    const requestBody = JSON.stringify({
      type: "anoncreds",
      anoncreds_credential_detail: {
        credential_definition_id: credentialDefinitionId,
        attributes: {
          date_of_birth: "1986-09-29",
          id_number: "8698989898989",
          country_of_birth: "South Africa",
          citizen_status: "Citizen",
          date_of_issue: dateOfIssue, // Use the parameter
          gender: "MALE",
          surname: "Doe",
          nationality: "South African",
          country_of_birth_iso_code: "ZA",
          names: "John James",
        },
      },
      save_exchange_record: false,
      connection_id: issuerConnectionId,
    });

    const response = http.post(url, requestBody, params);
    if (response.status >= 200 && response.status < 300) {
      return response;
    }
    console.error(`createCredential request failed with status ${response.status}`);
    if (response.body) {
      console.error(`Response body: ${response.body}`);
    }
    return response.body;
  } catch (error) {
    console.error(`Error accepting invitation: ${error.message}`);
    throw error;
  }
}

export function acceptCredential(holderAccessToken, credentialId) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/issuer/credentials/${credentialId}/request`;
  const params = {
    headers: {
      "x-api-key": holderAccessToken,
      "Content-Type": "application/json",
    },
  };

  try {
    const response = http.post(url, null, params);
    return response;
  } catch (error) {
    console.error(`Error accepting credential: ${error.message}`);
    throw error;
  }
}

export function createCredentialDefinition(
  issuerAccessToken,
  credDefTag,
  schemaId
) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/definitions/credentials`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
    },
    timeout: "120s",
  };

  try {
    // Construct the request body including the invitation object
    const requestBody = JSON.stringify({
      tag: credDefTag,
      schema_id: schemaId,
      support_revocation: true,
      revocation_registry_size: 100,
    });

    const response = http.post(url, requestBody, params);

    if (response.status == 200) {
      return response;
    }
    logError(response);
    console.warn(
      `Failed creating credential definition. Request Body: ${requestBody}`
    );
    return null;
  } catch (error) {
    console.error(`Error creating credential definition: ${error.message}`);
    throw error;
  }
}

export function getCredentialIdByThreadId(holderAccessToken, threadId) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/issuer/credentials`;
  const params = {
    headers: {
      "x-api-key": holderAccessToken,
      "Content-Type": "application/json",
    },
  };
  // console.log(`holderAccessToken: ${holderAccessToken}`);
  try {
    const response = http.get(url, params);
    // console.log(`Request headers: ${JSON.stringify(response.request.headers)}`);
    // Parse the response body
    const responseData = JSON.parse(response.body);
    // Iterate over the responseData array
    for (let i = 0; i < responseData.length; i++) {
      const obj = responseData[i];
      // Check if the current object has a matching thread_id
      if (obj.thread_id === threadId) {
        // Return the credential_id if a match is found
        return obj.credential_exchange_id;
      }
    }
    // Throw an error if no match is found
    throw new Error(
      `VU ${__VU}: Iteration ${__ITER}: No match found for threadId: ${threadId}\nResponse body: ${JSON.stringify(
        responseData,
        null,
        2
      )}`
    );
  } catch (error) {
    console.error(`VU ${__VU}: Iteration ${__ITER}: Error in getCredentialIdByThreadId:`, error);
    throw error; // Re-throw the error to propagate it to the caller
  }
}

export function getCredentialDefinitionId(
  issuerAccessToken,
  credDefTag,
  schemaVersion
) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/definitions/credentials?schema_version=${schemaVersion}`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
    },
  };

  const response = http.get(url, params);
  if (response.status >= 200 && response.status < 300) {
    const responseData = JSON.parse(response.body);
    const matchingItem = responseData.find((item) => item.tag === credDefTag);

    if (matchingItem) {
      log.info(`Credential definition found for tag ${credDefTag}: ${matchingItem.id}`);
      return matchingItem.id;
    }
    log.info(`Credential definition not found for tag ${credDefTag}`);
    return false;
  }
  logError(response);
  throw new Error("Failed to check credential definition existence");
}

export function sendProofRequest(issuerAccessToken, issuerConnectionId) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/verifier/send-request`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
      "Content-Type": "application/json",
    },
  };
  try {
    // Get current epoch time in seconds
    const currentEpochTimeSeconds = Math.floor(Date.now() / 1000);

    // Construct the request body including the invitation object
    const requestBody = {
      type: "anoncreds",
      anoncreds_proof_request: {
        non_revoked: {
          to: currentEpochTimeSeconds, // Current epoch time in seconds
        },
        requested_attributes: {
          get_id_number: { name: "id_number" },
        },
        requested_predicates: {},
      },
      save_exchange_record: true,
      comment: "string",
      connection_id: issuerConnectionId,
    };
    const response = http.post(url, JSON.stringify(requestBody), params);
    return response;
  } catch (error) {
    console.error(`Error accepting invitation: ${error.message}`);
    throw error;
  }
}

export function getProofIdByThreadId(holderAccessToken, threadId) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/verifier/proofs?thread_id=${threadId}`;
  const params = {
    headers: {
      "x-api-key": holderAccessToken,
      "Content-Type": "application/json",
    },
  };
  // console.log(`holderAccessToken: ${holderAccessToken}`);
  try {
    const response = http.get(url, params);
    // console.log(`Request headers: ${JSON.stringify(response.request.headers)}`);
    // Parse the response body
    const responseData = JSON.parse(response.body);
    // Iterate over the responseData array
    for (let i = 0; i < responseData.length; i++) {
      const obj = responseData[i];
      // Check if the current object has a matching thread_id
      if (obj.thread_id === threadId) {
        // Return the credential_id if a match is found
        // console.log(`Log of the request made: ${JSON.stringify(response.request)}`);
        return obj.proof_id;
      }
    }
    // Throw an error if no match is found
    throw new Error(
      `No match found for threadId: ${threadId}\nResponse body: ${JSON.stringify(
        responseData,
        null,
        2
      )}`
    );
  } catch (error) {
    console.error("Error in getProofId:", error);
    throw error; // Re-throw the error to propagate it to the caller
  }
}

export function getProofIdCredentials(holderAccessToken, proofId, dateOfIssue = null) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/verifier/proofs/${proofId}/credentials`;
  const params = {
    headers: {
      "x-api-key": holderAccessToken,
      "Content-Type": "application/json",
    },
  };
  // console.log(`holderAccessToken: ${holderAccessToken}`);
  try {
    const response = http.get(url, params);
    // console.log(`Request headers: ${JSON.stringify(response.request.headers)}`);
    // Parse the response body
    const responseData = JSON.parse(response.body);

    // If no dateOfIssue filter is provided, return the first credential (existing behavior)
    if (!dateOfIssue) {
      for (let i = 0; i < responseData.length; i++) {
        const obj = responseData[i];
        const credentialId = obj.cred_info.credential_id;
        // TODO: this will always return the first credentialId - fix this
        return credentialId;
      }
    } else {
      // Filter credentials by date_of_issue attribute
      for (let i = 0; i < responseData.length; i++) {
        const obj = responseData[i];
        const credAttrs = obj.cred_info.attrs || {};

        // Check if the credential has a date_of_issue attribute that matches
        if (credAttrs.date_of_issue === dateOfIssue.toString()) {
          const credentialId = obj.cred_info.credential_id;
          log.debug(`Found matching credential with date_of_issue: ${dateOfIssue}`);
          return credentialId;
        }
      }

      // If no matching credential found, log available credentials for debugging
      log.warn(`No credential found with date_of_issue: ${dateOfIssue}`);
      log.warn(`Available credentials: ${JSON.stringify(responseData.map(obj => ({
        credentialId: obj.cred_info.credential_id,
        dateOfIssue: obj.cred_info.attrs?.date_of_issue
      })), null, 2)}`);
    }

    // Throw an error if no match is found
    // console.log(`Log of the request made: ${JSON.stringify(response.request)}`);
    throw new Error(
      `No match found for proofId: ${proofId}${dateOfIssue ? ` with date_of_issue: ${dateOfIssue}` : ''}`
    );
  } catch (error) {
    log.error(`Error in getProofIdCredentials: Error message: ${error.message}`);
    throw error; // Re-throw the error to propagate it to the caller
  }
}

// tenant/v1/verifier/accept-request
export function acceptProofRequest(holderAccessToken, proofId, referent) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/verifier/accept-request`;
  const params = {
    headers: {
      "x-api-key": holderAccessToken,
      "Content-Type": "application/json",
    },
  };
  try {
    // Construct the request body including the invitation object
    const requestBody = {
      type: "anoncreds",
      proof_id: proofId,
      anoncreds_presentation_spec: {
        requested_attributes: {
          get_id_number: {
            cred_id: referent,
            revealed: true,
          },
        },
        requested_predicates: {},
        self_attested_attributes: {},
      },
      diff_presentation_spec: {},
    };

    const response = http.post(url, JSON.stringify(requestBody), params);
    // console.log(`holderAccessToken: ${holderAccessToken}`);
    // console.log(`Response body: ${response.body}`);
    // console.log(`Referent: ${referent}`);
    // console.log(`ProofId: ${proofId}`);
    return response;
  } catch (error) {
    console.error(`Error accepting proof request: ${error.message}`);
    throw error;
  }
}

export function getProof(issuerAccessToken, issuerConnectionId, proofThreadId) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/verifier/proofs?thread_id=${proofThreadId}`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
      "Content-Type": "application/json",
    },
  };
  try {
    // Construct the request body including the invitation object
    const requestBody = {
      type: "indy",
      indy_proof_request: {
        requested_attributes: {
          get_id_number: { name: "id_number" },
        },
        requested_predicates: {},
      },
      save_exchange_record: false,
      comment: "string",
      connection_id: issuerConnectionId,
    };
    const response = http.get(url, params);
    // console.log(`Response body: ${response.body}`);
    // console.log(`IssuerAccessToken: ${issuerAccessToken}`);
    // console.log(`IssuerConnectionId: ${issuerConnectionId}`);
    // console.log(`ProofThreadId: ${proofThreadId}`);
    return response;
  } catch (error) {
    console.error(`Error getting proof: ${error.message}`);
    throw error;
  }
}

export function getDocs() {
  const url = `${__ENV.CLOUDAPI_URL}/tenant-admin/docs`;
  const params = {
    headers: {
      "Content-Type": "application/json",
    },
  };
  try {
    const response = http.get(url, params);
    return response;
  } catch (error) {
    console.error(`Error getting docs: ${error.message}`);
    throw error;
  }
}

export function createSchema(headers, schemaName, schemaVersion) {
  const url = `${__ENV.CLOUDAPI_URL}/governance/v1/definitions/schemas`;
  const params = {
    headers: {
      ...headers,
    },
    timeout: "120s",
  };

  try {
    // Construct the request body including the invitation object
    const requestBody = JSON.stringify({
      name: schemaName,
      version: schemaVersion,
      schema_type: "anoncreds",
      attribute_names: [
        "date_of_birth",
        "id_number",
        "country_of_birth",
        "citizen_status",
        "date_of_issue",
        "gender",
        "surname",
        "nationality",
        "country_of_birth_iso_code",
        "names",
      ],
    });

    const response = http.post(url, requestBody, params);
    // console.log(`Response body: ${response.body}`);
    return response;
  } catch (error) {
    console.error(`Error creating schema: ${error.message}`);
    throw error;
  }
}

export function getSchema(headers, schemaName, schemaVersion) {
  const url = `${__ENV.CLOUDAPI_URL}/governance/v1/definitions/schemas?schema_name=${schemaName}&schema_version=${schemaVersion}`;
  const params = {
    headers: {
      ...headers,
    },
  };

  try {
    const response = http.get(url, params);
    // console.log(`Response XXX body: ${response.body}`);
    return response;
  } catch (error) {
    console.error(`Error getting schema: ${error.message}`);
    throw error;
  }
}

export function revokeCredential(issuerAccessToken, credentialExchangeId) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/issuer/credentials/revoke`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
      "Content-Type": "application/json",
    },
  };
  try {
    const requestBody = {
      credential_exchange_id: credentialExchangeId,
    };
    const response = http.post(url, JSON.stringify(requestBody), params);

    if (response.status !== 200) {
      log.error(`Unexpected status code: ${response.status}`);
      log.error(`VU ${__VU}: Iteration ${__ITER}: Response body: ${response.body}`);
    }

    return response;
  } catch (error) {
    log.error(`Error revoking credential: ${error.message}`);
    throw error;
  }
}

export function revokeCredentialAutoPublish(
  issuerAccessToken,
  credentialExchangeId
) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/issuer/credentials/revoke`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
      "Content-Type": "application/json",
    },
  };
  try {
    const requestBody = {
      credential_exchange_id: credentialExchangeId,
      auto_publish_on_ledger: true,
    };
    const response = http.post(url, JSON.stringify(requestBody), params);

    if (response.status !== 200) {
      log.error(`Unexpected status code: ${response.status}`);
      log.error(`Response body: ${response.body}`);
    }

    return response;
  } catch (error) {
    log.error(`Error revoking credential: ${error.message}`);
    throw error;
  }
}

export function publishRevocation(issuerAccessToken, fireAndForget = false) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/issuer/credentials/publish-revocations`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
      "Content-Type": "application/json",
    },
    timeout: fireAndForget ? "5s" : "120s",
  };

  try {
    const requestBody = {
      revocation_registry_credential_map: {},
    };
    const response = http.post(url, JSON.stringify(requestBody), params);

    if (fireAndForget) {
      console.log("Publish revocation request fired (fire-and-forget)");
      return true;
    }

    if (response.status !== 200) {
      console.error(`Unexpected status code: ${response.status}`);
      console.error(`Response body: ${response.body}`);
    }

    return response;
  } catch (error) {
    if (fireAndForget) {
      console.warn(`Fire-and-forget publish revocation failed: ${error.message}`);
      return false;
    }
    console.error(`Error revoking credential: ${error.message}`);
    throw error;
  }
}

export function checkRevoked(issuerAccessToken, credentialExchangeId) {
  const url = `${__ENV.CLOUDAPI_URL}/tenant/v1/issuer/credentials/revocation/record?credential_exchange_id=${credentialExchangeId}`;
  const params = {
    headers: {
      "x-api-key": issuerAccessToken,
      "Content-Type": "application/json",
    },
  };
  try {
    const response = http.get(url, params);
    return response;
  } catch (error) {
    console.error(`Error checking if credential is revoked: ${error.message}`);
    throw error;
  }
}

export function genericPolling({
  accessToken,
  walletId,
  topic,
  field,
  fieldId,
  state,
  lookBack = 60,
  maxAttempts = 3,
  sseTag,
  requestTimeout = 14 // max 14s - will need to deal with SSE ping at 15s
}) {
  const endpoint = `${__ENV.CLOUDAPI_URL}/tenant/v1/sse/${walletId}/${topic}/${field}/${fieldId}/${state}?look_back=${lookBack}`;

  // Backoff delays in seconds: 0.5, 1, 2, 5
  const delays = [0.5, 1, 2, 3];

  let attempts = 0;
  const startTime = new Date();

  while (attempts < maxAttempts) {

    // Get the appropriate delay based on attempt number
    const delayIndex = Math.min(attempts, delays.length - 1);
    const currentDelay = delays[delayIndex];

    // Make the HTTP request
    const response = http.get(endpoint, {
      headers: {
        "x-api-key": accessToken,
        "Content-Type": "application/json"
      },
      timeout: requestTimeout * 1000, // Convert seconds to milliseconds
      tags: sseTag ? { name: sseTag } : { name: `GET_${topic}_${state}_Event` }
    });

    log.debug(`Attempt: ${attempts} - Polling Response body: ${response.body}`);

    // TODO: if it is a connection error, back-off, else the fetch timeout serves as a back-off
    // Track success/failure metrics
    if (response.status !== 200) {
      if (attempts === maxAttempts - 1) {
        log.error(`HTTP request failed with status ${response.status}`);
      } else if (attempts > 0) {
        log.warn(`Attempt: ${attempts} HTTP request failed with status ${response.status}. Sleeping for ${currentDelay}s before next attempt`);
      }
      attempts++;
      sleep(currentDelay);
      continue;
    }

    try {
      // Handle SSE-style responses with "data:" prefix
      const trimmedBody = response.body.trim();
      let responseData;

      if (trimmedBody.startsWith('data:')) {
        // SSE format - parse the data after the prefix
        const dataContent = trimmedBody.substring(5).trim();
        responseData = JSON.parse(dataContent);
      } else if (trimmedBody.startsWith('{') || trimmedBody.startsWith('[')) {
        // Regular JSON
        responseData = JSON.parse(response.body);
      } else {
        if (attempts === maxAttempts - 1) {
          log.error(`Attempt: ${attempts} Response is not parseable: ${trimmedBody}.`);
        } else if (attempts > 0) {
          log.warn(`Attempt: ${attempts} Response is not parseable: ${trimmedBody}. Sleeping for ${currentDelay}s before next attempt`);
        }
        attempts++;
        sleep(currentDelay);
        continue;
      }

      // 1. SSE direct object: {wallet_id, topic, payload}
      if (responseData.topic === topic &&
          responseData.payload &&
          responseData.payload.state === state) {
        // First attempt - silent success
        if (attempts === 0) {
          log.debug(`Found direct event match on first attempt`);
          return true;
        }
        // Non-first attempt - log success
        log.info(`Found direct event match (attempt ${attempts+1})`);
        return true;
      }

      // If we reach here, no matching event was found
      if (attempts === maxAttempts - 1) {
        log.error(`No matching event found yet (attempt ${attempts+1})`);
      } else if (attempts > 0) {
        log.warn(`No matching event found yet (attempt ${attempts+1})`);
      }
    } catch (error) {
      if (attempts === maxAttempts - 1) {
        log.error(`Error parsing response: ${error.message}`);
        log.error(`Response body: ${response.body}`);
      } else if (attempts > 0) {
        log.warn(`Error parsing response: ${error.message}`);
        log.warn(`Response body: ${response.body}`);
      }
      attempts++;
      sleep(currentDelay);
      continue;
    }

    // Increment attempts and sleep before next attempt
    log.warn(`Failed to find matching event after ${maxAttempts} attempts. Sleeping for ${currentDelay}s before next attempt`);
    attempts++;
    if (attempts < maxAttempts) {
      sleep(currentDelay);
    }
  }

  // If we get here, we've exhausted all attempts
  log.error(`Failed to find matching event after ${maxAttempts} attempts`);
  return false;
}

export function genericWaitForSSEEvent({
  accessToken,
  walletId,
  threadId,
  eventType,
  sseUrlPath,
  topic,
  expectedState,
  lookBack = 45,
  maxRetries = 5,
  retryDelay = 2,
  maxEmptyPings = 3,
  sseTag,
  connectionTimeout = 29 // Default timeout in seconds, set slightly below Docker's 30s
}) {
  const tmpUrl = `https://waypoint.cloudapi.stage.didx.co.za/sse/${walletId}/${sseUrlPath}/${threadId}/${eventType}?look_back=${lookBack}`;
  const sseUrl = `${__ENV.CLOUDAPI_URL}/tenant/v1/sse/${walletId}/${sseUrlPath}/${threadId}/${eventType}?look_back=${lookBack}`;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
      if (attempt > 0) {
          console.warn(`VU ${__VU}: Iteration ${__ITER}: genericWaitForSSEEvent Retry attempt ${attempt}/${maxRetries}`);
          console.log(`curl -i -H "x-api-key: ${accessToken}" ${tmpUrl}`);
          console.log(`curl -i -H "x-api-key: ${accessToken}" ${sseUrl}`);
          sleep(retryDelay);
      }

      let succeeded = false;
      let failed = false;
      let emptyPingCount = 0;
      let hadEmptyPing = false;

      // Track connection timing
      const startTime = new Date();
      let connectionDuration = 0;

      try {
          const response = sse.open(
              sseUrl,
              {
                  headers: { "x-api-key": accessToken },
                  tags: sseTag ? { k6_sse_tag: sseTag } : undefined
              },
              (client) => {
                  client.on("event", (event) => {
                      // Calculate current connection duration
                      connectionDuration = (new Date() - startTime) / 1000;

                      if (!event.data || event.data.trim() === "") {
                          emptyPingCount++;
                          hadEmptyPing = true;
                          console.log(`VU ${__VU}: Iteration ${__ITER}: genericWaitForSSEEvent Empty ping received: ${emptyPingCount} (connection time: ${connectionDuration.toFixed(2)}s)`);
                          if (emptyPingCount >= maxEmptyPings) {
                              console.error(`VU ${__VU}: Iteration ${__ITER}: genericWaitForSSEEvent Failed after ${maxEmptyPings} empty pings (connection time: ${connectionDuration.toFixed(2)}s)`);
                              client.close();
                              failed = true;
                              return false;
                          }
                          return;
                      }

                      try {
                          const eventData = JSON.parse(event.data);
                          if (eventData &&
                              eventData.topic === topic &&
                              eventData.payload &&
                              eventData.payload.state === expectedState) {
                              if (hadEmptyPing) {
                                  console.log(`VU ${__VU}: Iteration ${__ITER}: genericWaitForSSEEvent Successfully received event after ${emptyPingCount} empty ping(s) (connection time: ${connectionDuration.toFixed(2)}s)`);
                              }
                              client.close();
                              succeeded = true;
                          }
                      } catch (error) {
                          console.error(`VU ${__VU}: Iteration ${__ITER}: genericWaitForSSEEvent Failed to parse event: ${error.message} (connection time: ${connectionDuration.toFixed(2)}s)`);
                          client.close();
                          failed = true;
                      }
                  });

                  client.on("error", (error) => {
                      connectionDuration = (new Date() - startTime) / 1000;
                      const errorMessage = error.error ? error.error() : 'Unknown error';
                      console.error(`VU ${__VU}: Iteration ${__ITER}: genericWaitForSSEEvent SSE connection error: ${errorMessage} (connection time: ${connectionDuration.toFixed(2)}s)`);
                      client.close();
                      failed = true;
                  });
              }
          );

          if (!response) {
              connectionDuration = (new Date() - startTime) / 1000;
              console.warn(`VU ${__VU}: Iteration ${__ITER}: SSE connection failed completely - no response object returned (connection time: ${connectionDuration.toFixed(2)}s)`);
              continue;
          } else if (response.status !== 200) {
              connectionDuration = (new Date() - startTime) / 1000;
              const errorDetails = response.error ? response.error : 'none';
              const isTimeout = errorDetails.includes('timeout') ||
                                 (response.error && response.error.message && response.error.message.includes('timeout'));

              console.warn(`VU ${__VU}: Iteration ${__ITER}: SSE connection failed with status: ${response.status} (connection time: ${connectionDuration.toFixed(2)}s)`);

              // Enhanced timeout detection and reporting
              if (isTimeout) {
                  console.warn(`VU ${__VU}: Iteration ${__ITER}: TIMEOUT DETECTED: Connection timed out after ${connectionDuration.toFixed(2)}s (server timeout may be set to ${connectionTimeout}s)`);

                  // Add system info that might help diagnose network issues
                  console.warn(`VU ${__VU}: Iteration ${__ITER}: Network diagnostic info:
                      - Connection target: host.docker.internal (docker network bridge)
                      - VU ID: ${__VU}
                      - Execution environment: ${__ENV.K6_EXECUTION_ENV || 'unknown'}
                      - OS: ${__ENV.OS || 'unknown'}
                  `);
              }

              // Log more details about the response
              console.warn(`VU ${__VU}: Iteration ${__ITER}: Response details:
                  - Body: ${response.body ? response.body : 'undefined'}
                  - Headers: ${JSON.stringify(response.headers)}
                  - Error: ${errorDetails}
                  - URL: ${sseUrl}
                  - Timestamp: ${new Date().toISOString()}
                  - Connection duration: ${connectionDuration.toFixed(2)}s`);
              continue;
          }

          // Monitor connection time while waiting for events
          const maxWaitTime = 30; // seconds to wait before logging a warning about long-running connection
          let waitCounter = 0;
          const waitInterval = 2; // Check every 2 seconds

          while (!succeeded && !failed && attempt < maxRetries) {
              sleep(waitInterval);
              waitCounter += waitInterval;
              connectionDuration = (new Date() - startTime) / 1000;

              // Log a warning if connection is taking too long
              if (waitCounter % maxWaitTime === 0) {
                  console.warn(`VU ${__VU}: Iteration ${__ITER}: SSE connection still waiting after ${connectionDuration.toFixed(2)}s - no events received yet`);
              }

              // Check if we're approaching timeout
              if (connectionDuration > (connectionTimeout * 0.8) && !succeeded && !failed) {
                  console.warn(`VU ${__VU}: Iteration ${__ITER}: SSE connection approaching timeout (${connectionDuration.toFixed(2)}s / ${connectionTimeout}s)`);
              }
          }

      } catch (e) {
          connectionDuration = (new Date() - startTime) / 1000;
          console.error(`VU ${__VU}: Iteration ${__ITER}: Unexpected error in SSE connection: ${e.message} (connection time: ${connectionDuration.toFixed(2)}s)`);

          // Check if this is the first attempt
          if (attempt === 0) {
              // Add DNS lookup verification
              try {
                  const dnsStart = new Date();
                  const dnsResponse = http.get("http://host.docker.internal:8000", {
                      timeout: 2000,
                      headers: { "x-api-key": accessToken }
                  });
                  const dnsTime = (new Date() - dnsStart) / 1000;
                  console.log(`VU ${__VU}: Iteration ${__ITER}: DNS verification: status=${dnsResponse.status}, time=${dnsTime.toFixed(2)}s`);
              } catch (dnsError) {
                  console.warn(`VU ${__VU}: Iteration ${__ITER}: DNS verification failed: ${dnsError.message}`);
              }
          }

          failed = true;
      }

      // If we failed due to empty pings, exit immediately
      if (failed && emptyPingCount >= maxEmptyPings) {
          return false;
      }

      if (succeeded) {
          connectionDuration = (new Date() - startTime) / 1000;
          if (attempt > 0) {
              console.log(`VU ${__VU}: Iteration ${__ITER}: genericWaitForSSEEvent Reconnection attempt ${attempt} was successful (total time: ${connectionDuration.toFixed(2)}s)`);
          }
          return true;
      }

      if (failed) {
          continue;
      }
  }

  console.error(`VU ${__VU}: Iteration ${__ITER}: genericWaitForSSEEvent SSE connection failed after ${maxRetries} retries for event type: ${eventType}, state: ${expectedState}, topic: ${topic}, threadId: ${threadId}`);
  return false;
}

export function retry(fn, retries = 3, delay = 2000, operation = 'Undefined') {
  let attempts = 0;

  while (attempts < retries) {
    try {
      const result = fn();
      // If first attempt succeeds, just return the result without logging
      if (attempts === 0) {
        return result;
      }
      // For subsequent successful attempts, log the success
      log.info(`Operation ${operation}: Succeeded on attempt ${attempts + 1}`);
      return result;
    } catch (e) {
      attempts++;
      // Log from first unsuccessful second attempt onwards
      if (attempts < retries) {
        log.warn(`Operation ${operation}: Attempt ${attempts}/${retries} failed: ${e.message}`);
      }

      if (attempts >= retries) {
        log.error(`Operation ${operation}: All ${attempts}/${retries} attempts failed`);
        throw e;
      }

      sleep(delay / 1000);
    }
  }
}

export function pollAndCheck(pollingConfig, context) {
  const response = genericPolling(pollingConfig);

  // Generate check message from perspective, topic, and state
  // e.g., "Holder credentials done event received successfully"
  const checkMessage = `${context.perspective} ${pollingConfig.topic} ${pollingConfig.state} event received successfully`;

  check(response, {
    [checkMessage]: (r) => r === true
  });

  return response;
}
