/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import { Counter } from "k6/metrics";
import { getBearerToken } from "../libs/auth.js";
import {
  acceptProofRequest,
  genericWaitForSSEEvent,
  getProof,
  getProofIdByThreadId,
  getProofIdCredentials,
  getWalletIndex,
  sendProofRequest,
  retry,  // Add this import
  genericPolling,
} from "../libs/functions.js";

const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const holderPrefix = __ENV.HOLDER_PREFIX;
const issuerPrefix = __ENV.ISSUER_PREFIX;
const outputPrefix = `${issuerPrefix}-${holderPrefix}`;
const version = __ENV.VERSION;

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
    // "http_req_duration{scenario:default}": ["max>=0"],
    // "http_reqs{scenario:default}": ["count >= 0"],
    // "iteration_duration{scenario:default}": ["max>=0"],
    // 'specific_function_reqs{my_custom_tag:specific_function}': ['count>=0'],
    // checks: ["rate==1"],
    checks: ["rate>0.99"],
    // 'specific_function_reqs{scenario:default}': ['count>=0'],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "create-proofs",
    version: `${version}`,
  },
};

const testFunctionReqs = new Counter("test_function_reqs");

const inputFilepath = `../output/${outputPrefix}-create-invitation.json`;
const data = open(inputFilepath, "r");

// const specificFunctionReqs = new Counter('specific_function_reqs');

// const mainIterationDuration = new Trend('main_iteration_duration');

function shuffleArray(array) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
}

export function setup() {
  const bearerToken = getBearerToken();

  let tenants = data.trim().split("\n").map(JSON.parse);
  tenants = shuffleArray(tenants);

  return { bearerToken, tenants };
}

export default function (data) {
  const bearerToken = data.bearerToken;
  const tenants = data.tenants;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);
  const wallet = tenants[walletIndex];

  // console.log(`wallet.issuer_connection_id: ${wallet.issuer_connection_id}`);
  // const sendProofRequestResponse = sendProofRequest(issuer.accessToken, wallet.issuer_connection_id);
  // console.log(`VU: ${__VU}, Iteration: ${__ITER}, Issuer Wallet ID: ${wallet.issuer_wallet_id}`);
  let sendProofRequestResponse;
  try {
    sendProofRequestResponse = retry(() => {
      const response = sendProofRequest(
        wallet.issuer_access_token,
        wallet.issuer_connection_id
      );
      if (response.status !== 200) {
        throw new Error(`Non-200 status: ${response.status}`);
      }
      return response;
    }, 5, 2000);
  } catch (error) {
    console.error(`Failed after retries: ${error.message}`);
    sendProofRequestResponse = error.response || error;
  }
  check(sendProofRequestResponse, {
    "Proof request sent successfully": (r) => {
      if (r.status !== 200) {
        throw new Error(
          `Unexpected response while sending proof request: ${r.response}`
        );
      }
      return true;
    },
  });

  const { thread_id: threadId } = JSON.parse(sendProofRequestResponse.body);

  const waitForSSEEventReceivedResponse = genericPolling({
    accessToken: wallet.access_token,
    walletId: wallet.wallet_id,
    threadId: threadId,
    eventType: "request-received",
    sseUrlPath: "proofs/thread_id",
    topic: "proofs",
    expectedState: "request-received",
    maxAttempts: 10,  // Will use backoff: 0.5s, 1s, 2s, 5s, 10s, 15s
    lookBack: 60,
    sseTag: "proof_request_received",
  });

  const sseEventError = "SSE event was not received successfully";
  const sseCheckMessage = "SSE Event received successfully: request-recevied";

  check(waitForSSEEventReceivedResponse, {
    [sseCheckMessage]: (r) => r === true
});

  // check(waitForSSEEventReceivedResponse, {
  //   "SSE Event received successfully: request-recevied": (r) => {
  //     if (!r) {
  //       throw new Error("SSE event was not received successfully");
  //     }
  //     return true;
  //   },
  // });

  // sleep(2);

  // TODO: return object and add check for the response
  const proofId = getProofIdByThreadId(wallet.access_token, threadId);
  // console.log(`Proof ID: ${proofId}`);

  let credentialId;
  try {
    credentialId = retry(() => {
      const response = getProofIdCredentials(wallet.access_token, proofId);
      if (response.length === 0) {
        console.log('Credential ID:', response);
        throw new Error('No credential ID returned');
      }
      return response;
    }, 5, 2000, 'Get credential ID');
  } catch (error) {
    console.error(`Failed to get proof credentials after retries: ${error.message}`);
    throw error; // Re-throw as this is required for the next steps
  }

  let acceptProofResponse;
  try {
    acceptProofResponse = retry(() => {
      const response = acceptProofRequest(
        wallet.access_token,
        proofId,
        credentialId
      );
      if (response.status !== 200) {
        throw new Error(`Non-200 status: ${response.status}`);
      }
      return response;
    }, 5, 2000);
  } catch (error) {
    console.error(`Failed after retries: ${error.message}`);
    acceptProofResponse = error.response || error;
  }
  check(acceptProofResponse, {
    "Proof accepted successfully": (r) => {
      if (r.status !== 200) {
        throw new Error(
          `Unexpected response while accepting proof: ${r.response}`
        );
      }
      return true;
    },
  });

  // console.log(`Initiate wait for SSE event: done`);
  const waitForSSEProofDoneRequest = genericPolling({
    accessToken: wallet.access_token,
    walletId: wallet.wallet_id,
    threadId: threadId,
    eventType: "done",
    sseUrlPath: "proofs/thread_id",
    topic: "proofs",
    expectedState: "done",
    maxAttempts: 10,  // Will use backoff: 0.5s, 1s, 2s, 5s, 10s, 15s
    lookBack: 60,
    sseTag: "proof_done",
  });

  const sseEventErrorProofDone = "SSE event was not received successfully";
  const sseCheckMessageProofDone = "SSE Event received successfully: done";

  check(waitForSSEProofDoneRequest, {
    [sseCheckMessageProofDone]: (r) => r === true
  });

  // check(waitForSSEProofDoneRequest, {
  //   "SSE Proof Request state: done": (r) => {
  //     if (!r) {
  //       throw new Error("SSE proof done was not successful");
  //     }
  //     return true;
  //   },
  // });

  // const getProofResponse = getProof(issuer.accessToken, wallet.issuer_connection_id, threadId );
  let getProofResponse;
  try {
    getProofResponse = getProof(
      wallet.issuer_access_token,
      wallet.issuer_connection_id,
      threadId
    );
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
      throw new Error(
        `Credential is not verified. Current verification status: ${responseBody[0].verified}`
      );
    }
    return true;
  };

  const unverifiedCheck = (r) => {
    if (r.status !== 200) {
      throw new Error(`Unexpected response while getting proof: ${r.response}`);
    }
    const responseBody = JSON.parse(r.body);
    if (responseBody[0].verified !== false) {
      throw new Error(
        `Credential is not unverified. Current verification status: ${responseBody[0].verified}`
      );
    }
    return true;
  };

  check(getProofResponse, {
    [__ENV.IS_REVOKED === "true"
      ? "Proof received and unverified"
      : "Proof received and verified"]:
      __ENV.IS_REVOKED === "true" ? unverifiedCheck : verifiedCheck,
  });

  testFunctionReqs.add(1);
}
