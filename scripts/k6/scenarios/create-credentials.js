/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check } from "k6";
import { Counter } from "k6/metrics";
import file from "k6/x/file";
import { getBearerToken } from "../libs/auth.js";
import {
  acceptCredential,
  createCredential,
  genericWaitForSSEEvent,
  getCredentialIdByThreadId,
  getWalletIndex,
} from "../libs/functions.js";

const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const holderPrefix = __ENV.HOLDER_PREFIX;
const issuerPrefix = __ENV.ISSUER_PREFIX;
const outputPrefix = `${issuerPrefix}-${holderPrefix}`;

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
    test_phase: "create-credentials",
  },
};

const inputFilepath = `../output/${outputPrefix}-create-invitation.json`;
const data = open(inputFilepath, "r");
const outputFilepath = `output/${outputPrefix}-create-credentials.json`;

// Helper function to get the issuer index using pre-calculated assignments
function getIssuerIndex(vu, iter) {
  const walletIndex = getWalletIndex(vu, iter);
  return issuerAssignments[walletIndex];
}
// const specificFunctionReqs = new Counter('specific_function_reqs');
const testFunctionReqs = new Counter("test_function_reqs");
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

  file.writeString(outputFilepath, "");
  let holders = data.trim().split("\n").map(JSON.parse);
  holders = shuffleArray(holders); // Randomize the order of holders

  return { bearerToken, holders };
}

export default function (data) {
  const bearerToken = data.bearerToken;
  const holders = data.holders;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);
  const wallet = holders[walletIndex];

  // console.log(`VU: ${__VU}, Iteration: ${__ITER}, Wallet Index: ${walletIndex}, Issuer Wallet ID: ${wallet.issuer_wallet_id}`);

  let createCredentialResponse;
  try {
    createCredentialResponse = createCredential(
      bearerToken,
      wallet.issuer_access_token,
      wallet.issuer_credential_definition_id,
      wallet.issuer_connection_id
    );
  } catch (error) {
    // console.error(`Error creating credential: ${error.message}`);
    createCredentialResponse = { status: 500, response: error.message };
  }

  check(createCredentialResponse, {
    "Credential created successfully": (r) => {
      if (r.status !== 200) {
        console.error(
          `Unexpected response while creating credential: ${r.response}`
        );
        return false;
      }
      return true;
    },
  });

  const { thread_id: threadId, credential_exchange_id: credentialExchangeId } =
    JSON.parse(createCredentialResponse.body);

  // console.log(`Thread ID: ${threadId}`);
  // console.log(`Holer access token: ${wallet.holder_access_token}`);
  // console.log(`Wallet ID: ${wallet.wallet_id}`);

  const waitForSSEEventResponse = genericWaitForSSEEvent({
    accessToken: wallet.access_token,
    walletId: wallet.wallet_id,
    threadId: threadId,
    eventType: "offer-received",
    sseUrlPath: "credentials/thread_id",
    topic: "credentials",
    expectedState: "offer-received",
    maxDuration: 10,
    sseTag: "credential_offer_received",
  });

  const sseEventError = "SSE event was not received successfully";
  const sseCheckMessage = "SSE request received successfully: offer-received";

  check(waitForSSEEventResponse, {
      [sseCheckMessage]: (r) => r === true
  });

  // console.log(`VU ${__VU}: Iteration ${__ITER}: Accepting credential for thread ID: ${threadId}`);

  const credentialId = getCredentialIdByThreadId(wallet.access_token, threadId);

  const acceptCredentialResponse = acceptCredential(
    wallet.access_token,
    credentialId
  );
  check(acceptCredentialResponse, {
    "Credential accepted successfully": (r) => {
      if (r.status !== 200) {
        throw new Error(
          `Unexpected response while accepting credential: ${r.response}`
        );
      }
      return true;
    },
  });

  const issuerData = JSON.stringify({
    credential_exchange_id: credentialExchangeId,
    issuer_access_token: wallet.issuer_access_token,
    issuer_credential_definition_id: wallet.issuer_credential_definition_id,
    issuer_connection_id: wallet.issuer_connection_id,
  });
  file.appendString(outputFilepath, `${issuerData}\n`);

  // specificFunctionReqs.add(1, { my_custom_tag: 'specific_function' });

  // const end = Date.now();
  // const duration = end - start;
  // console.log(`Duration for iteration ${__ITER}: ${duration} ms`);
  // mainIterationDuration.add(duration);
  // sleep(1);
  testFunctionReqs.add(1);
}
