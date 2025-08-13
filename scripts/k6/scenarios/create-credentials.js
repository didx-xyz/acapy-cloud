/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import { Counter } from "k6/metrics";
import file from "k6/x/file";
import { log, shuffleArray } from "../libs/k6Functions.js";
import {
  acceptCredential,
  createCredential,
  getCredentialIdByThreadId,
  getWalletIndex,
  retry,
  pollAndCheck,
} from "../libs/functions.js";
import { config } from "../libs/config.js";

const vus = config.test.vus;
const iterations = config.test.iterations;
const holderPrefix = config.test.holderPrefix;
const issuerPrefix = config.test.issuerPrefix;
const outputPrefix = `${issuerPrefix}-${holderPrefix}`;
const version = config.test.version;
const sleepDuration = config.test.sleepDuration;

export const options = {
  scenarios: {
    default: {
      executor: "per-vu-iterations",
      vus,
      iterations,
      maxDuration: "24h",
    },
  },
  setupTimeout: "180s",
  teardownTimeout: "180s",
  maxRedirects: 4,
  thresholds: {
    // https://community.grafana.com/t/ignore-http-calls-made-in-setup-or-teardown-in-results/97260/2
    "http_req_duration{scenario:default}": ["max>=0"],
    "http_reqs{scenario:default}": ["count >= 0"],
    "iteration_duration{scenario:default}": ["max>=0"],
    checks: ["rate>0.99"],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "create-credentials",
    version: `${version}`,
  },
};

const inputFilepath = `../output/${outputPrefix}-create-invitation.jsonl`;
const data = open(inputFilepath, "r");
const outputFilepath = `output/${outputPrefix}-create-credentials.jsonl`;
const epochOutputFilepath = `output/${outputPrefix}-epoch-timestamps.jsonl`;

// Helper function to get the issuer index using pre-calculated assignments
function getIssuerIndex(vu, iter) {
  const walletIndex = getWalletIndex(vu, iter);
  return issuerAssignments[walletIndex];
}
const testFunctionReqs = new Counter("test_function_reqs");

export function setup() {
  file.writeString(outputFilepath, "");

  // Generate current epoch timestamp (10 digits)
  const currentEpoch = Math.floor(Date.now() / 1000);

  // Write epoch timestamp to file
  file.writeString(epochOutputFilepath, JSON.stringify({ epoch_timestamp: currentEpoch }) + "\n");

  let invitations = data.trim().split("\n").map(JSON.parse);
  invitations = shuffleArray(invitations); // Randomize the order of invitations

  return { invitations, epochTimestamp: currentEpoch };
}

export default function (data) {
  const invitations = data.invitations;
  const epochTimestamp = data.epochTimestamp;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);
  const invitation = invitations[walletIndex];

  log.debug(`Wallet Index: ${walletIndex}, Issuer Wallet ID: ${invitation.issuer_wallet_id}`);

  let createCredentialResponse;
  try {
    createCredentialResponse = retry(() => {
      const response = createCredential(
        invitation.issuer_access_token,
        invitation.issuer_credential_definition_id,
        invitation.issuer_connection_id,
        epochTimestamp.toString() // Pass epoch timestamp as date_of_issue
      );
      if (response.status !== 200) {
        throw new Error(`Non-200 status: ${response.status}`);
      }
      return response;
    }, 5, 5000, "createCredentialResponse");
  } catch (error) {
    console.error(`Failed after retries: ${error.message}`);
    createCredentialResponse = error.response || error;
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

  const { thread_id: threadId, credential_exchange_id: issuerCredentialExchangeId } =
    JSON.parse(createCredentialResponse.body);

  log.debug(`walletIndex: ${walletIndex}, walletId: ${invitation.wallet_id} issuerConnectionId: ${invitation.issuer_connection_id}`);

  pollAndCheck({
    accessToken: invitation.access_token,
    walletId: invitation.wallet_id,
    topic: "credentials",
    field: "thread_id",
    fieldId: threadId,
    state: "offer-received",
    // maxAttempts: 10,
    lookBack: 60,
    sseTag: "credential_offer_received",
  }, { perspective: "Holder" });

  log.debug(`Accepting credential for thread ID: ${threadId}`);

  const holderCredentialExchangeId = getCredentialIdByThreadId(invitation.access_token, threadId);

  let acceptCredentialResponse;
  try {
    acceptCredentialResponse = retry(() => {
      const response = acceptCredential(invitation.access_token, holderCredentialExchangeId);
      if (response.status !== 200) {
        throw new Error(`Non-200 status: ${response.status}`);
      }
      return response;
    }, 5, 2000);
  } catch (error) {
    console.error(`Failed after retries: ${error.message}`);
    acceptCredentialResponse = error.response || error;
  }

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

  pollAndCheck({
    accessToken: invitation.access_token,
    walletId: invitation.wallet_id,
    topic: "credentials",
    field: "credential_exchange_id",
    fieldId: holderCredentialExchangeId,
    state: "done",
    // maxAttempts: 10,
    lookBack: 60,
    sseTag: "credential_received",
  }, { perspective: "Holder" });

  const issuerData = JSON.stringify({
    issuer_wallet_name: invitation.issuer_wallet_name,
    issuer_wallet_id: invitation.issuer_wallet_id,
    credential_exchange_id: issuerCredentialExchangeId,
    issuer_access_token: invitation.issuer_access_token,
    issuer_credential_definition_id: invitation.issuer_credential_definition_id,
    issuer_connection_id: invitation.issuer_connection_id,
    date_of_issue: epochTimestamp, // Include the epoch timestamp in output. Currently redundant, but potentially useful for future reference
  });
  file.appendString(outputFilepath, `${issuerData}\n`);
  testFunctionReqs.add(1);
  sleep(sleepDuration);
}
