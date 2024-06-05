import http from 'k6/http';
import sse from "k6/x/sse"
import { check } from 'k6';

// export function checkTenantExists(bearerToken, wallet) {
//   const url = `https://${__ENV.cloudapi_url}/tenant-admin/v1/tenants?wallet_name=${wallet}`;
//   const params = {
//     headers: {
//       'Authorization': `Bearer ${bearerToken}`,
//       'Content-Type': 'application/json'
//     }
//   };

//   try {
//     let response = http.get(url, params);

//     if (response.status >= 200 && response.status < 300) {
//       // Request was successful
//       const responseData = JSON.parse(response.body)[0]; // Take the first item of the array
//       const walletId = responseData?.wallet_id; // Use optional chaining

//       if (walletId !== undefined) {
//         console.log('wallet_id is already defined - skipping Issuer creation...');
//       } else {
//         console.log('wallet_id is undefined');
//       }
//       return walletId;
//     } else {
//       // Request failed
//       console.error(`Request failed with status ${response.status}`);
//       console.error(`Response body: ${response.body}`);
//       return null;
//     }
//   } catch (error) {
//     // Handle any errors that occurred during the request
//     console.error(`Error checking if tenant exists: ${error.message}`);
//     throw error;
//   }
// }

export function createTenant(bearerToken, wallet) {
  const url = `https://${__ENV.cloudapi_url}/tenant-admin/v1/tenants`;
  const payload = JSON.stringify({
    wallet_label: wallet.wallet_label,
    wallet_name: wallet.wallet_name,
    group_id: "Some Group Id",
    image_url: "https://upload.wikimedia.org/wikipedia/commons/7/70/Example.png"
  });

  const params = {
    headers: {
      'Authorization': `Bearer ${bearerToken}`,
      'Content-Type': 'application/json'
    }
  };

  try {
    let response = http.post(url, payload, params);

    if (response.status >= 200 && response.status < 300) {
      // Request was successful
      const responseData = JSON.parse(response.body);
      const walletId = responseData.wallet_id;
      const accessToken = responseData.access_token;

      // Store walletId and accessToken for the current VU and iteration
      const vuKey = `vu_${__VU}`;
      const iterKey = `iter_${__ITER}`;

      if (!global[vuKey]) {
        global[vuKey] = {};
      }

      global[vuKey][iterKey] = {
        walletId: walletId,
        accessToken: accessToken
      };

      return response;
    } else {
      // Request failed
      console.error(`Request failed with status ${response.status}`);
      console.error(`Response body: ${response.body}`);
      throw new Error(`Failed to create tenant: ${response.status}`);
    }
  } catch (error) {
    // Handle any errors that occurred during the request
    console.error(`Error creating tenant: ${error.message}`);
    throw error;
  }
}

export function getWalletIdByWalletName(bearerToken, walletName) {
  const url = `https://${__ENV.cloudapi_url}/tenant-admin/v1/tenants?wallet_name=${walletName}`;
  const params = {
    headers: {
      'Authorization': `Bearer ${bearerToken}`,
    },
  };

  try {
    let response = http.get(url, params);

    if (response.status >= 200 && response.status < 300) {
      // Request was successful
      const responseData = JSON.parse(response.body);

      // Check if the response is an array and take the first item
      if (Array.isArray(responseData) && responseData.length > 0) {
        const firstItem = responseData[0];
        let walletId;

        // Safely access wallet_id without optional chaining
        if (firstItem && firstItem.hasOwnProperty('wallet_id')) {
          walletId = firstItem.wallet_id;
        }

        if (walletId) {
          return walletId;
        } else {
          console.warn(`No wallet_id found in the response for wallet_name ${walletName}`);
        }
      } else {
        console.warn(`Unexpected response format for wallet_name ${walletName}: ${response.body}`);
      }
    } else {
      // Request failed
      console.error(`Request failed with status ${response.status}`);
      console.error(`Response body: ${response.body}`);
      throw new Error(`Failed to get access token: ${response.status}`);
    }
  } catch (error) {
    // Handle any errors that occurred during the request
    console.error(`Error getting access token: ${error.message}`);
    throw error;
  }
}

export function getAccessTokenByWalletId(bearerToken, walletId) {
  const url = `https://${__ENV.cloudapi_url}/tenant-admin/v1/tenants/${walletId}/access-token`;

  const params = {
    headers: {
      'Authorization': `Bearer ${bearerToken}`,
    },
  };

  let response = http.get(url, params);

  if (response.status >= 200 && response.status < 300) {
    // Request was successful
    const responseData = JSON.parse(response.body);
    const accessToken = responseData.access_token;
    return accessToken;
  } else {
    // Request failed
    console.error(`Request failed with status ${response.status}`);
    console.error(`Response body: ${response.body}`);
    // throw new Error(`Failed to get access token: ${response.body}`);
    return response.body;
  }
}

export function deleteTenant(bearerToken, walletId) {
  const url = `https://${__ENV.cloudapi_url}/tenant-admin/v1/tenants/${walletId}`;
  const params = {
    headers: {
      'Authorization': `Bearer ${bearerToken}`,
    },
  };

  try {
    let response = http.del(url, null, params);
    const responseBody = response.body;

    if (response.status === 200) {
      // Request was successful
      if (responseBody === 'null') {
        console.log(`Wallet ${walletId} deleted successfully.`);
      } else {
        console.error(`Failed to delete wallet ${walletId}. Response body: ${responseBody}`);
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

export function createIssuerTenant(bearerToken, walletName) {
  const url = `https://${__ENV.cloudapi_url}/tenant-admin/v1/tenants`;
  const payload = JSON.stringify({
    wallet_label: walletName,
    wallet_name: walletName,
    roles: ["issuer", "verifier"],
    group_id: "Group A",
    image_url: "https://upload.wikimedia.org/wikipedia/commons/7/70/Example.png"
  });
  const params = {
    headers: {
      'Authorization': `Bearer ${bearerToken}`,
      'Content-Type': 'application/json'
    }
  };

  try {
    let response = http.post(url, payload, params);
    return response;
  } catch (error) {
    console.error(`Error creating issuer tenant: ${error.message}`);
    throw error;
  }
}

export function createInvitation(bearerToken, issuerAccessToken) {
  const url = `https://${__ENV.cloudapi_url}/tenant/v1/connections/create-invitation`;
  const params = {
    headers: {
      'Authorization': `Bearer ${bearerToken}`,
      'x-api-key': issuerAccessToken
    }
  };

  try {
    let response = http.post(url, null, params);
    return response;
  } catch (error) {
    console.error(`Error creating invitation: ${error.message}`);
    throw error;
  }
}

export function acceptInvitation(holderAccessToken, invitationObj) {
  const url = `https://${__ENV.cloudapi_url}/tenant/v1/connections/accept-invitation`;
  const params = {
    headers: {
      'x-api-key': holderAccessToken,
      'Content-Type': 'application/json'
    }
  };

  try {
    // Construct the request body including the invitation object
    const requestBody = {
      "alias": "holder <> issuer",
      "invitation": invitationObj
    };

    let response = http.post(url, JSON.stringify(requestBody), params);
    return response;
  } catch (error) {
    console.error(`Error accepting invitation: ${error.message}`);
    throw error;
  }
}

export function createCredential(bearerToken, issuerAccessToken, credentialDefinitionId, issuerConnectionId) {
  const url = `https://${__ENV.cloudapi_url}/tenant/v1/issuer/credentials`;
  const params = {
    headers: {
      'Authorization': `Bearer ${bearerToken}`,
      'x-api-key': issuerAccessToken
    }
  };

  try {
    // Construct the request body including the invitation object
    const requestBody = JSON.stringify({
      "type": "indy",
      "indy_credential_detail": {
        "credential_definition_id": credentialDefinitionId,
        "attributes": {
          "speed":"9001"
        }
      },
      "save_exchange_record": false,
      "connection_id": issuerConnectionId,
      "protocol_version": "v2"
    });

    console.log(`credentialDefinitionId: ${credentialDefinitionId}`)
    console.log(`issuerConnectionId: ${issuerConnectionId}`)
    console.log(`Request body: ${requestBody}`);

    let response = http.post(url, requestBody, params);
    if (response.status >= 200 && response.status < 300) {
      // Request was successful
      return response;
    } else {
      console.error(`Request failed with status ${response.status}`);
      console.error(`Response body: ${response.body}`);
      return response.body;
    }
  } catch (error) {
    console.error(`Error accepting invitation: ${error.message}`);
    throw error;
  }
}

export function acceptCredential(holderAccessToken, credentialId) {
  const url = `https://${__ENV.cloudapi_url}/tenant/v1/issuer/credentials/${credentialId}/request`;
  const params = {
    headers: {
      'x-api-key': holderAccessToken,
      'Content-Type': 'application/json'
    }
  };

  try {
    let response = http.post(url, null, params);
    return response;
  } catch (error) {
    console.error(`Error accepting credential: ${response}`);
    throw error;
  }
}

export function createCredentialDefinition(bearerToken, issuerAccessToken) {
  const url = `https://${__ENV.cloudapi_url}/tenant/v1/definitions/credentials`;
  const params = {
    headers: {
      'Authorization': `Bearer ${bearerToken}`,
      'x-api-key': issuerAccessToken
    }
  };

  try {
    // Construct the request body including the invitation object
    const requestBody = JSON.stringify({
      "tag": "k6",
      "schema_id": "Bo9W24g9VmLCnWopu5LJJm:2:ritalin:0.1.0",
      "support_revocation": true,
      "revocation_registry_size": 100
    });

    let response = http.post(url, requestBody, params);
    return response;
  } catch (error) {
    console.error(`Error creating credential definition: ${error.message}`);
    throw error;
  }
}

export function getCredentialIdByThreadId(holderAccessToken, threadId) {
  const url = `https://${__ENV.cloudapi_url}/tenant/v1/issuer/credentials`;
  const params = {
    headers: {
      'x-api-key': holderAccessToken,
      'Content-Type': 'application/json'
    }
  };
  console.log(`holderAccessToken: ${holderAccessToken}`);
  try {
    let response = http.get(url, params);
    console.log(`Request headers: ${JSON.stringify(response.request.headers)}`);
    // Parse the response body
    let responseData = JSON.parse(response.body);
    // Iterate over the responseData array
    for (let i = 0; i < responseData.length; i++) {
      let obj = responseData[i];
      // Check if the current object has a matching thread_id
      if (obj.thread_id === threadId) {
        // Return the credential_id if a match is found
        return obj.credential_id;
      }
    }
    // Throw an error if no match is found, including the response body
    throw new Error(`No match found for threadId: ${threadId}\nResponse body: ${JSON.stringify(responseData, null, 2)}`);
  } catch (error) {
    console.error("Error in getCredentialIdByThreadId:", error);
    throw error; // Re-throw the error to propagate it to the caller
  }
}

export function waitForSSEEvent(holderAccessToken, holderWalletId, threadId) {
  const sseUrl = `https://${__ENV.cloudapi_url}/tenant/v1/sse/${holderWalletId}/credentials/thread_id/${threadId}/offer-received`;
  const headers = {
    'x-api-key': holderAccessToken,
  };

  let eventReceived = false;

  const response = sse.open(sseUrl, {
    headers: headers,
    tags: { 'k6_sse_tag': 'credential_offer_received' },
  }, function (client) {
    client.on('event', function (event) {
      console.log(`event data=${event.data}`);
      const eventData = JSON.parse(event.data);
      if (eventData.topic === 'credentials' && eventData.payload.state === 'offer-received') {
        check(eventData, {
          'Event received': (e) => e.payload.state === 'offer-received',
        });
        eventReceived = true;
        client.close();
      }
    });

    client.on('error', function (e) {
      console.log('An unexpected error occurred: ', e.error());
      client.close();
    });
  });

  check(response, { 'SSE connection established': (r) => r && r.status === 200 });

  // Wait for the event to be received or a maximum duration
  const maxDuration = 10000; // 10 seconds
  const checkInterval = 1000; // 1 second
  let elapsedTime = 0;

  while (!eventReceived && elapsedTime < maxDuration) {
    console.log(`Waiting for event... Elapsed time: ${elapsedTime}ms`);
    elapsedTime += checkInterval;
    sleep(checkInterval);
  }

  return eventReceived;
}

export function waitForSSEEventConnection(holderAccessToken, holderWalletId, invitationConnectionId) {
  const sseUrl = `https://${__ENV.cloudapi_url}/tenant/v1/sse/${holderWalletId}/connections/connection_id/${invitationConnectionId}/completed`;
  const headers = {
    'x-api-key': holderAccessToken,
  };

  let eventReceived = false;

  const response = sse.open(sseUrl, {
    headers: headers,
    tags: { 'k6_sse_tag': 'connection_ready' },
  }, function (client) {
    client.on('event', function (event) {
      console.log(`event data=${event.data}`);
      const eventData = JSON.parse(event.data);
      if (eventData.topic === 'connections' && eventData.payload.state === 'completed') {
        check(eventData, {
          'Event received': (e) => e.payload.state === 'completed',
        });
        eventReceived = true;
        client.close();
      }
    });

    client.on('error', function (e) {
      console.log('An unexpected error occurred: ', e.error());
      client.close();
    });
  });

  check(response, { 'SSE connection established': (r) => r && r.status === 200 });

  // Wait for the event to be received or a maximum duration
  const maxDuration = 10000; // 10 seconds
  const checkInterval = 1000; // 1 second
  let elapsedTime = 0;

  while (!eventReceived && elapsedTime < maxDuration) {
    console.log(`Waiting for event... Elapsed time: ${elapsedTime}ms`);
    elapsedTime += checkInterval;
    sleep(checkInterval);
  }

  return eventReceived;
}