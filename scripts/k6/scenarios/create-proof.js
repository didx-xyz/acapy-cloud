/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import { SharedArray } from "k6/data";
import { Counter, Trend } from "k6/metrics";
import { getBearerToken } from "../libs/auth.js";
import {
  acceptProofRequest,
  createCredentialDefinition,
  deleteTenant,
  getCredentialDefinitionId,
  getProof,
  getProofIdByThreadId,
  getProofIdCredentials,
  getWalletIdByWalletName,
  sendProofRequest,
  waitForSSEEventReceived,
  waitForSSEProofDone,
} from "../libs/functions.js";
import { createIssuerIfNotExists } from "../libs/issuerUtils.js";
import { createSchemaIfNotExists } from "../libs/schemaUtils.js";

const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const issuerPrefix = __ENV.ISSUER_PREFIX;

export const options = {
  scenarios: {
    default: {
      executor: "per-vu-iterations",
      vus,
      iterations,
      maxDuration: "24h",
    },
  },
  setupTimeout: "180s", // Increase the setup timeout to 120 seconds
  teardownTimeout: "180s", // Increase the teardown timeout to 120 seconds
  maxRedirects: 4,
  thresholds: {
    // https://community.grafana.com/t/ignore-http-calls-made-in-setup-or-teardown-in-results/97260/2
    "http_req_duration{scenario:default}": ["max>=0"],
    "http_reqs{scenario:default}": ["count >= 0"],
    "iteration_duration{scenario:default}": ["max>=0"],
    checks: ["rate==1"],
    // 'specific_function_reqs{my_custom_tag:specific_function}': ['count>=0'],
    // 'specific_function_reqs{scenario:default}': ['count>=0'],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "create-proofs",
  },
};

const inputFilepath = "../output/create-invitation.json";
const data = open(inputFilepath, "r");

// const specificFunctionReqs = new Counter('specific_function_reqs');
const testFunctionReqs = new Counter("test_function_reqs");
// const mainIterationDuration = new Trend('main_iteration_duration');

// Seed data: Generating a list of options.iterations unique wallet names
// const wallets = new SharedArray('wallets', function() {
//   const walletsArray = [];
//   for (let i = 0; i < options.iterations; i++) {
//     walletsArray.push({
//       wallet_label: `xk6 holder ${i}`,
//       wallet_name: `xk6_wallet_${i}`
//     });
//   }
//   return walletsArray;
// });

const numIssuers = 1;
const issuers = [];

export function setup() {
  const bearerToken = getBearerToken();
  const issuers = [];

  const holders = data.trim().split("\n").map(JSON.parse);

  // // Example usage of the loaded data
  // holders.forEach((holderData) => {
  //   console.log(`Processing wallet ID: ${holderData.wallet_id}`);
  //   // Your test logic here, e.g., make HTTP requests using the holderData
  // });

  for (let i = 0; i < numIssuers; i++) {
    const walletName = `${issuerPrefix}_${i}`;
    const credDefTag = walletName;

    const issuerData = createIssuerIfNotExists(bearerToken, walletName);
    check(issuerData, {
      "Issuer data retrieved successfully": (data) => data !== null && data !== undefined,
    });
    if (!issuerData) {
      console.error(`Failed to create or retrieve issuer for ${walletName}`);
      continue;
    }
    const { issuerWalletId, issuerAccessToken } = issuerData;

    const credentialDefinitionId = getCredentialDefinitionId(bearerToken, issuerAccessToken, credDefTag);
    if (credentialDefinitionId) {
      console.log(`Credential definition already exists for issuer ${walletName} - Skipping creation`);
      issuers.push({
        walletId: issuerWalletId,
        accessToken: issuerAccessToken,
        credentialDefinitionId,
      });
      continue;
    }
    console.warn(`Failed to get credential definition ID for issuer ${walletName}`);
    // console.error(`Response body: ${credentialDefinitionId.body}`);

    const schemaId = createSchemaIfNotExists(governanceBearerToken, schemaName, schemaVersion);
    check(schemaId, {
      "Schema ID is not null": (id) => id !== null && id !== undefined,
    });

    const createCredentialDefinitionResponse = createCredentialDefinition(
      bearerToken,
      issuerAccessToken,
      credDefTag,
      schemaId,
    );
    check(createCredentialDefinitionResponse, {
      "Credential definition created successfully": (r) => r.status === 200,
    });

    if (createCredentialDefinitionResponse.status === 200) {
      const { id: credentialDefinitionId } = JSON.parse(createCredentialDefinitionResponse.body);
      console.log(`Credential definition created successfully for issuer ${walletName}`);
      issuers.push({
        walletId: issuerWalletId,
        accessToken: issuerAccessToken,
        credentialDefinitionId,
      });
    } else {
      console.error(`Failed to create credential definition for issuer ${walletName}`);
    }
  }

  return { bearerToken, issuers, holders };
}

const iterationsPerVU = options.scenarios.default.iterations;
// Helper function to calculate the wallet index based on VU and iteration
function getWalletIndex(vu, iter) {
  const walletIndex = (vu - 1) * iterationsPerVU + (iter - 1);
  return walletIndex;
}

//random number between 0 and 100 (including 0 and 100 as options)
function getRandomInt() {
  return Math.floor(Math.random() * 101);
}

export default function (data) {
  // const start = Date.now();
  const bearerToken = data.bearerToken;
  const issuers = data.issuers;
  const holders = data.holders;
  const walletIndex = getWalletIndex(__VU, __ITER + 1); // __ITER starts from 0, adding 1 to align with the logic
  const wallet = holders[walletIndex];

  const issuerIndex = __ITER % numIssuers;
  const issuer = issuers[issuerIndex];

  // console.log(`isser.accessToken: ${issuer.accessToken}`);
  // console.log(`issuer.credentialDefinitionId: ${issuer.credentialDefinitionId}`);
  // console.log(`wallet.issuer_connection_id: ${wallet.issuer_connection_id}`);
  // const sendProofRequestResponse = sendProofRequest(issuer.accessToken, wallet.issuer_connection_id);
  let sendProofRequestResponse;
  try {
    sendProofRequestResponse = sendProofRequest(issuer.accessToken, wallet.issuer_connection_id);
  } catch (error) {
    // console.error(`Error creating credential: ${error.message}`);
    sendProofRequestResponse = { status: 500, response: error.message };
  }
  check(sendProofRequestResponse, {
    "Proof request sent successfully": (r) => {
      if (r.status !== 200) {
        throw new Error(`Unexpected response while sending proof request: ${r.response}`);
      }
      return true;
    },
  });

  const { thread_id: threadId } = JSON.parse(sendProofRequestResponse.body);

  const waitForSSEEventReceivedResponse = waitForSSEEventReceived(wallet.access_token, wallet.wallet_id, threadId);
  check(waitForSSEEventReceivedResponse, {
    "SSE Event received successfully: request-recevied": (r) => {
      if (!r) {
        throw new Error("SSE event was not received successfully");
      }
      return true;
    },
  });

  // TODO: return object and add check for the response
  const proofId = getProofIdByThreadId(wallet.access_token, threadId);
  const referent = getProofIdCredentials(wallet.access_token, proofId);

  const acceptProofResponse = acceptProofRequest(wallet.access_token, proofId, referent);
  check(acceptProofResponse, {
    "Proof accepted successfully": (r) => {
      if (r.status !== 200) {
        throw new Error(`Unexpected response while accepting proof: ${r.response}`);
      }
      return true;
    },
  });

  const waitForSSEProofDoneRequest = waitForSSEProofDone(issuer.accessToken, issuer.walletId, threadId);
  check(waitForSSEProofDoneRequest, {
    "SSE Proof Request state: done": (r) => {
      if (!r) {
        throw new Error("SSE proof done was not successful");
      }
      return true;
    },
  });

  // const getProofResponse = getProof(issuer.accessToken, wallet.issuer_connection_id, threadId );
  let getProofResponse;
  try {
    getProofResponse = getProof(issuer.accessToken, wallet.issuer_connection_id, threadId);
  } catch (error) {
    // console.error(`Error creating credential: ${error.message}`);
    getProofResponse = { status: 500, response: error.message };
  }

  const verifiedCheck = (r) => {
    if (r.status !== 200) {
      throw new Error(`Unexpected response while getting proof: ${r.response}`);
    }
    const responseBody = JSON.parse(r.body);
    if (responseBody[0].verified !== true) {
      throw new Error(`Credential is not verified. Current verification status: ${responseBody[0].verified}`);
    }
    return true;
  };

  const unverifiedCheck = (r) => {
    if (r.status !== 200) {
      throw new Error(`Unexpected response while getting proof: ${r.response}`);
    }
    const responseBody = JSON.parse(r.body);
    if (responseBody[0].verified !== false) {
      throw new Error(`Credential is not unverified. Current verification status: ${responseBody[0].verified}`);
    }
    return true;
  };

  check(getProofResponse, {
    [__ENV.IS_REVOKED === "true" ? "Proof received and unverified" : "Proof received and verified"]:
      __ENV.IS_REVOKED === "true" ? unverifiedCheck : verifiedCheck,
  });

  testFunctionReqs.add(1);
}
