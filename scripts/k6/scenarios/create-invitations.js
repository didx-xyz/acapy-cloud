/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";
import { log } from "../libs/k6Functions.js";
import file from "k6/x/file";
import {
  acceptInvitation,
  createInvitation,
  getWalletIndex,
  retry,
  getIssuerPublicDid,
  createDidExchangeRequest,
  getIssuerConnectionId,
  pollAndCheck,
  getHolderConnections,
} from "../libs/functions.js";

const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const issuerPrefix = __ENV.ISSUER_PREFIX;
const holderPrefix = __ENV.HOLDER_PREFIX;
const schemaName = __ENV.SCHEMA_NAME;
const schemaVersion = __ENV.SCHEMA_VERSION;
const numIssuers = __ENV.NUM_ISSUERS;
const outputPrefix = `${issuerPrefix}-${holderPrefix}`;
const version = __ENV.VERSION;
const useOobInvitation = __ENV.OOB_INVITATION === "true";

export const options = {
  scenarios: {
    default: {
      executor: "per-vu-iterations",
      vus,
      iterations,
      maxDuration: "24h",
    },
  },
  setupTimeout: "120s",
  teardownTimeout: "120s",
  maxRedirects: 4,
  thresholds: {
    // https://community.grafana.com/t/ignore-http-calls-made-in-setup-or-teardown-in-results/97260/2
    checks: ["rate>0.99"],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "create-invitation",
    version: `${version}`,
  },
};

const testFunctionReqs = new Counter("test_function_reqs");     // successful completions
const inputFilepath = `../output/${holderPrefix}-create-holders.jsonl`;
const inputFilepathIssuer = `../output/${issuerPrefix}-create-issuers.jsonl`;
const data = open(inputFilepath, "r");
const dataIssuer = open(inputFilepathIssuer, "r");
const outputFilepath = `output/${outputPrefix}-create-invitation.jsonl`;

export function setup() {
  const holders = data.trim().split("\n").map(JSON.parse);
  const issuers = dataIssuer.trim().split("\n").map(JSON.parse);
  file.writeString(outputFilepath, "");

  const walletName = issuerPrefix;

  return { issuers, holders };
}

function getIssuerIndex(vu, iter) {
  const numIssuers = __ENV.NUM_ISSUERS;
  return (vu + iter - 2) % numIssuers;
}

export default function (data) {

  const issuers = data.issuers;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);

  const holders = data.holders;
  const holder = holders[walletIndex];

  const issuerIndex = getIssuerIndex(__VU, __ITER + 1);
  const issuer = issuers[issuerIndex];

  log.debug(`Wallet Index: ${walletIndex}, Issuer Index: ${issuerIndex}, Issuer Wallet ID: ${issuer.wallet_id}`);

  let publicDidResponse;
  try {
    publicDidResponse = retry(() => {
      const response = getIssuerPublicDid(issuer.access_token);
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


  let holderConnectionId;
  let invitationMsgId;

  if (useOobInvitation) {
    // OOB Invitation flow
    console.debug("Using OOB Invitation flow");
    let createOobInvitationResponse;
    try {
      createOobInvitationResponse = retry(() => {
        const response = createInvitation(issuer.access_token, issuerPublicDid);
        if (response.status !== 200) {
          throw new Error(`createOobInvitationResponse Non-200 status: ${response.body}`);
        }
        return response;
      }, 5, 2000);
    } catch (e) {
      console.error(`Failed after retries: ${e.message}`);
      createOobInvitationResponse = e.response || e;
    }

    check(createOobInvitationResponse, {
      "Invitation created successfully": (r) => {
        if (r.status !== 200) {
          throw new Error(
            `Unexpected response status while creating invitation:\nStatus: ${r.status}\nBody: ${r.body}`
          );
        }
        return true;
      },
    });

    const { invitation: invitationObj } = JSON.parse(createOobInvitationResponse.body);

    const acceptInvitationResponse = acceptInvitation(
      holder.access_token,
      invitationObj
    );

    check(acceptInvitationResponse, {
      "Invitation accepted successfully": (r) => {
        if (r.status !== 200) {
          throw new Error(
            `Unexpected response while accepting invitation:\nStatus: ${r.status}\nBody: ${r.body}`
          );
        }
        return true;
      },
    });

    holderConnectionId = JSON.parse(acceptInvitationResponse.body).connection_id;

    let getHolderPrivateDidResponse;
    try {
      getHolderPrivateDidResponse = retry(() => {
        const response = getHolderConnections(holder.access_token, holderConnectionId);
        if (response.status !== 200) {
          throw new Error(`getHolderPrivateDidResponse Non-200 status: ${response.body}`);
        }
        return response;
      }, 5, 2000);
    } catch (e) {
      console.error(`Failed after retries: ${e.message}`);
      getHolderPrivateDidResponse = e.response || e;
    }
    check(getHolderPrivateDidResponse, {
      "Holder Private DID retrieved successfully": (r) => {
        if (r.status !== 200) {
          throw new Error(
            `Unexpected response status while getting holder private DID:\nStatus: ${r.status}\nBody: ${r.body}`
          );
        }
        return true;
      },
    });

    const { invitation_msg_id: invitationMsgIdTemp } = JSON.parse(getHolderPrivateDidResponse.body);
    invitationMsgId = invitationMsgIdTemp;

  } else {
    // DIDExchange flow
    console.debug("Using DIDExchange flow");
    let createInvitationResponse;
    try {
      createInvitationResponse = retry(() => {
        const response = createDidExchangeRequest(holder.access_token, issuerPublicDid);
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
    const { invitation_msg_id: invitationMsgIdTemp, connection_id: holderConnectionIdTemp } = JSON.parse(createInvitationResponse.body);
    invitationMsgId = invitationMsgIdTemp;
    holderConnectionId = holderConnectionIdTemp;
  }

  pollAndCheck({
    accessToken: holder.access_token,
    walletId: holder.wallet_id,
    topic: "connections",
    field: "connection_id",
    fieldId: holderConnectionId,
    state: "completed",
    maxAttempts: 3,
    lookBack: 60,
    sseTag: "holder-connection-ready"
  }, { perspective: "Holder" });

  pollAndCheck({
    accessToken: issuer.access_token,
    walletId: issuer.wallet_id,
    topic: "connections",
    field: "invitation_msg_id",
    fieldId: invitationMsgId,
    state: "completed",
    maxAttempts: 3,
    lookBack: 60,
    sseTag: "issuer-connection-ready"
  }, { perspective: "Issuer" });

  // Issuer is now going to check
  // sleep(2);
  let getIssuerConnectionIdResponse;
  try {
    getIssuerConnectionIdResponse = retry(() => {
      const response = getIssuerConnectionId(issuer.access_token, invitationMsgId);
      if (response.status !== 200) {
        throw new Error(`getIssuerConnectionId Non-200 status: ${response.status} ${response.body}`);
      }
      if (response.body === "[]") {
        throw new Error(`getIssuerConnectionId: Empty response body: ${response.body}`);
      }
      return response;
    }
    , 5, 1000, "getIssuerConnectionId");
  }
  catch (e) {
    console.error(`Failed after retries: ${e.message}`);
    getIssuerConnectionIdResponse = e.response || e;
  }

  // log.debug(`Issuer connection ID Response Body: ${getIssuerConnectionIdResponse.body}`);
  const [{ connection_id: issuerConnectionId }] = JSON.parse(getIssuerConnectionIdResponse.body);

  const connectionData = JSON.stringify({
    wallet_label: holder.wallet_label,
    wallet_name: holder.wallet_name,
    wallet_id: holder.wallet_id,
    access_token: holder.access_token,
    connection_id: holderConnectionId,
    issuer_connection_id: issuerConnectionId,
    issuer_wallet_name: issuer.wallet_name,
    issuer_wallet_id: issuer.wallet_id,
    issuer_access_token: issuer.access_token,
    issuer_credential_definition_id: issuer.credential_definition_id,
  });
  file.appendString(outputFilepath, `${connectionData}\n`);

  testFunctionReqs.add(1);  // Count successful completions with tag
}
