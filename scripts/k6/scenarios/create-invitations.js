/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check } from "k6";
import { Counter, Trend } from "k6/metrics";
import file from "k6/x/file";
import { getBearerToken } from "../libs/auth.js";
import {
  acceptInvitation,
  createInvitation,
  genericWaitForSSEEvent,
  getWalletIndex,
  retry,
  getIssuerPublicDid,
  createDidExchangeRequest,
  getIssuerConnectionId,
} from "../libs/functions.js";
import { bootstrapIssuer } from "../libs/setup.js";
// import bootstrapIssuer from "./bootstrap-issuer.js";

const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const issuerPrefix = __ENV.ISSUER_PREFIX;
const holderPrefix = __ENV.HOLDER_PREFIX;
const schemaName = __ENV.SCHEMA_NAME;
const schemaVersion = __ENV.SCHEMA_VERSION;
const numIssuers = __ENV.NUM_ISSUERS;
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
  setupTimeout: "120s", // Increase the setup timeout to 120 seconds
  teardownTimeout: "120s", // Increase the teardown timeout to 120 seconds
  maxRedirects: 4,
  thresholds: {
    // https://community.grafana.com/t/ignore-http-calls-made-in-setup-or-teardown-in-results/97260/2
    // "http_req_duration{scenario:default}": ["max>=0"],
    // "http_reqs{scenario:default}": ["count >= 0"],
    // "http_reqs{my_custom_tag:specific_function}": ["count>=0"],
    // "iteration_duration{scenario:default}": ["max>=0"],
    checks: ["rate>0.99"],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "create-invitation",
    version: `${version}`,
  },
};

const testFunctionReqs = new Counter("test_function_reqs");     // successful completions
// const mainIterationDuration = new Trend("main_iteration_duration");

const inputFilepath = `../output/${holderPrefix}-create-holders.json`;
const inputFilepathIssuer = `../output/${issuerPrefix}-create-issuers.json`;
const data = open(inputFilepath, "r");
const dataIssuer = open(inputFilepathIssuer, "r");
const outputFilepath = `output/${outputPrefix}-create-invitation.json`;

export function setup() {
  const bearerToken = getBearerToken();
  const holders = data.trim().split("\n").map(JSON.parse);
  const issuers = dataIssuer.trim().split("\n").map(JSON.parse);
  file.writeString(outputFilepath, "");

  const walletName = issuerPrefix;
  // const credDefTag = walletName;
  // const issuers = bootstrapIssuer(
  //   numIssuers,
  //   walletName,
  //   credDefTag,
  //   schemaName,
  //   schemaVersion
  // );

  // if (!issuers || issuers.length === 0) {
  //   console.error("Failed to bootstrap issuers.");
  // }

  return { bearerToken, issuers, holders };
}

function getIssuerIndex(vu, iter) {
  const numIssuers = __ENV.NUM_ISSUERS;
  return (vu + iter - 2) % numIssuers;
}

// const vuStartTimes = {};

export default function (data) {

  // if (__ITER === 0) {
  //   vuStartTimes[__VU] = Date.now();
  // }
  const start = Date.now();
  const bearerToken = data.bearerToken;
  const issuers = data.issuers;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);

  // console.log(`VU: ${__VU}, Iteration: ${__ITER}, Wallet Index: ${walletIndex}`);

  const holders = data.holders;
  const wallet = holders[walletIndex];

  // const issuerIndex = __ITER % numIssuers;
  const issuerIndex = getIssuerIndex(__VU, __ITER + 1);
  const issuer = issuers[issuerIndex];

  // console.log(`VU: ${__VU}, Iteration: ${__ITER}, Wallet Index: ${walletIndex}, Issuer Index: ${issuerIndex}, Issuer Wallet ID: ${issuer.walletId}`);

  let publicDidResponse;
  try {
    publicDidResponse = retry(() => {
      const response = getIssuerPublicDid(issuer.accessToken);
      if (response.status !== 200) {
        throw new Error(`publicDidResponse: Non-200 status: ${response.body}`);
      }
      return response;
    }, 5, 2000);
  } catch (e) {
    console.error(`Failed after retries: ${e.message}`);
    publicDidResponse = e.response || e;
  }

  check(publicDidResponse, {
    "Public DID retrieved successfully": (r) => {
      if (r.status !== 200) {
        throw new Error(
          `Unexpected response status while getting public DID:\nStatus: ${r.status}\nBody: ${r.body}`
        );
      }
      return true;
    },
  });

  const { did: issuerPublicDid } = JSON.parse(publicDidResponse.body);


  let createInvitationResponse;
  try {
    createInvitationResponse = retry(() => {
      const response = createDidExchangeRequest(wallet.access_token, issuerPublicDid);
      if (response.status !== 200) {
        throw new Error(`createInvitationResponse Non-200 status: ${response.body}`);
      }
      return response;
    }, 5, 2000);
  } catch (e) {
    console.error(`Failed after retries: ${e.message}`);
    createInvitationResponse = e.response || e;
  }
  check(createInvitationResponse, {
    "Invitation created successfully": (r) => {
      if (r.status !== 200) {
        throw new Error(
          `Unexpected response status while create invitation:\nStatus: ${r.status}\nBody: ${r.body}`
        );
      }
      return true;
    },
  });
  const { my_did: holderDid, connection_id: holderConnectionId } =
    JSON.parse(createInvitationResponse.body);

  const waitForSSEEventResponse = genericWaitForSSEEvent({
    accessToken: wallet.access_token,
    walletId: wallet.wallet_id,
    threadId: holderConnectionId,
    eventType: "completed",
    sseUrlPath: "connections/connection_id",
    topic: "connections",
    expectedState: "completed",
    maxDuration: 60,
    // maxRetries: 30,
    // retryDelay: 2,
    // lookBack: 20,
    sseTag: "connection_ready",
  });

  const sseEventError = "SSE event was not received successfully";
  const sseCheckMessage = "SSE Event received successfully: connection-ready";

  check(waitForSSEEventResponse, {
    [sseCheckMessage]: (r) => r === true
  });

  // Issuer is now going to check

  let getIssuerConnectionIdResponse;
  try {
    getIssuerConnectionIdResponse = retry(() => {
      const response = getIssuerConnectionId(issuer.accessToken, holderDid);
      if (response.status !== 200) {
        throw new Error(`getIssuerConnectionId Non-200 status: ${response.status} ${response.body}`);
      }
      return response;
    }
    , 5, 2000);
  }
  catch (e) {
    console.error(`Failed after retries: ${e.message}`);
    getIssuerConnectionIdResponse = e.response || e;
  }

  const [{ connection_id: issuerConnectionId }] = JSON.parse(getIssuerConnectionIdResponse.body);

  const holderData = JSON.stringify({
    wallet_label: wallet.wallet_label,
    wallet_name: wallet.wallet_name,
    wallet_id: wallet.wallet_id,
    access_token: wallet.access_token,
    connection_id: holderConnectionId,
    issuer_connection_id: issuerConnectionId,
    issuer_wallet_name: issuer.walletName,
    issuer_wallet_id: issuer.walletId,
    issuer_access_token: issuer.accessToken,
    issuer_credential_definition_id: issuer.credentialDefinitionId,
  });
  file.appendString(outputFilepath, `${holderData}\n`);

  testFunctionReqs.add(1);  // Count successful completions with tag
}
