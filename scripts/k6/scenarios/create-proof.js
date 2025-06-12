/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep, fail } from "k6";
import { Counter } from "k6/metrics";
import file from "k6/x/file";
import {
  acceptProofRequest,
  getProof,
  getProofIdByThreadId,
  getProofIdCredentials,
  getWalletIndex,
  sendProofRequest,
  retry,
  pollAndCheck,
} from "../libs/functions.js";
import { log, shuffleArray } from "../libs/k6Functions.js";

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
  setupTimeout: "180s",
  teardownTimeout: "180s",
  maxRedirects: 4,
  thresholds: {
    // https://community.grafana.com/t/ignore-http-calls-made-in-setup-or-teardown-in-results/97260/2
    checks: ["rate>0.99"],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: __ENV.IS_REVOKED === "true" ? "create-proofs-unverified" : "create-proofs-verified",
    version: `${version}`,
  },
};

const testFunctionReqs = new Counter("test_function_reqs");

const inputFilepath = `../output/${outputPrefix}-create-invitation.jsonl`;
const data = open(inputFilepath, "r");
// Add path to epoch timestamps file
const epochInputFilepath = `../output/${outputPrefix}-epoch-timestamps.jsonl`;
// Read epoch data in init stage
let epochData = null;
try {
  epochData = open(epochInputFilepath, "r");
} catch (error) {
  console.warn(`Could not read epoch timestamp file: ${error.message}`);
}

export function setup() {
  let tenants = data.trim().split("\n").map(JSON.parse);
  tenants = shuffleArray(tenants);

  // Parse the epoch timestamp from the data read in init stage
  let epochTimestamp = null;
  try {
    if (epochData && epochData.trim()) {
      const epochJson = JSON.parse(epochData.trim().split('\n')[0]);
      epochTimestamp = epochJson.epoch_timestamp;
      console.debug(`Loaded epoch timestamp: ${epochTimestamp}`); // can't use custom logger in setup becuase ITER is unavailable
    }
  } catch (error) {
    console.warn(`Could not parse epoch timestamp: ${error.message}`);
  }

  return { tenants, epochTimestamp };
}

export default function (data) {
  const tenants = data.tenants;
  const epochTimestamp = data.epochTimestamp;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);
  const wallet = tenants[walletIndex];

  // const sendProofRequestResponse = sendProofRequest(issuer.accessToken, wallet.issuer_connection_id);
  log.debug(`walletIndex: ${walletIndex}, walletId: ${wallet.wallet_id}, issuerConnectionId: ${wallet.issuer_connection_id}, issuerAccessToken: ${wallet.issuer_access_token}`);
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
    }, 5, 2000, "Send proof request");
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

  pollAndCheck({
    accessToken: wallet.access_token,
    walletId: wallet.wallet_id,
    topic: "proofs",
    field: "thread_id",
    fieldId: threadId,
    state: "request-received",
    maxAttempts: 1,
    lookBack: 60,
    sseTag: "proof_request_received",
  }, { perspective: "Holder" });

  // TODO: return object and add check for the response
  const proofId = getProofIdByThreadId(wallet.access_token, threadId);
  // console.log(`Proof ID: ${proofId}`);

  let credentialId;
  try {
    credentialId = retry(() => {
      return getProofIdCredentials(wallet.access_token, proofId, epochTimestamp);
    }, 5, 10000, 'Get credential ID');
  } catch (error) {
    console.error(`Failed to get proof credentials after retries: ${error.message}`);
  }

  check(credentialId, {
    "Credential ID retrieved successfully": (r) => {
      if (!r || r.length === 0) {  // Check if r exists first, if undefined will exit on TypeError
        fail("Credential ID retrieval failed - exiting iteration"); // Exit the iteration if credential ID is not found - no point in continuing
      }
      return true;
    },
  });

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

  pollAndCheck({
    accessToken: wallet.access_token,
    walletId: wallet.wallet_id,
    topic: "proofs",
    field: "thread_id",
    fieldId: threadId,
    state: "done",
    // maxAttempts: 3,
    lookBack: 60,
    sseTag: "proof_done",
  }, { perspective: "Holder" });

  // const getProofResponse = getProof(issuer.accessToken, wallet.issuer_connection_id, threadId );
  let getProofResponse;
  try {
    getProofResponse = retry(() => {
      const response = getProof(
        wallet.issuer_access_token,
        wallet.issuer_connection_id,
        threadId
      );
      if (response.status !== 200) {
        throw new Error(`Non-200 status: ${response.status}`);
      }
      return response;
    }, 5, 2000, "Get proof");
  } catch (error) {
    console.error(`Failed to get proof after retries: ${error.message}`);
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
      log.debug(`Wallet Index: ${walletIndex}, Issuer Connection ID: ${wallet.issuer_connection_id}`);
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
