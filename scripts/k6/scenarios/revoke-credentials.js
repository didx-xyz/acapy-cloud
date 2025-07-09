/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import { Counter } from "k6/metrics";
import {
  checkRevoked,
  getWalletIndex,
  revokeCredentialAutoPublish,
  revokeCredential,
  publishRevocation,
} from "../libs/functions.js";
import { log } from "../libs/k6Functions.js";

const holderPrefix = __ENV.HOLDER_PREFIX;
const issuerPrefix = __ENV.ISSUER_PREFIX;
const outputPrefix = `${issuerPrefix}-${holderPrefix}`;

const inputFilepath = `../output/${outputPrefix}-create-credentials.jsonl`;
const data = open(inputFilepath, "r");

const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const testFunctionReqs = new Counter("test_function_reqs");
const sleepDuration = Number.parseInt(__ENV.SLEEP_DURATION, 0);

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
    "http_req_duration{scenario:default}": ["max>=0"],
    "http_reqs{scenario:default}": ["count >= 0"],
    "iteration_duration{scenario:default}": ["max>=0"],
    checks: ["rate==1"],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "revoke-credentials",
    version: `${version}`,
  },
};

export function setup() {
  const issuers = data.trim().split("\n").map(JSON.parse);
  return { issuers };
}

export default function (data) {
  const issuers = data.issuers;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);
  const issuer = issuers[walletIndex];

  // Check environment variable to determine revocation method
  const useAutoPublish =
    __ENV.USE_AUTO_PUBLISH === "true" ||
    __ENV.USE_AUTO_PUBLISH === undefined;

  let revokeCredentialResponse;

  if (useAutoPublish) {
    // Option A: Use auto-publish (full flow)
    revokeCredentialResponse = revokeCredentialAutoPublish(
      issuer.issuer_access_token,
      issuer.credential_exchange_id
    );
    check(revokeCredentialResponse, {
      "Credential revoked successfully": (r) => {
        if (r.status !== 200) {
          throw new Error(
            `VU ${__VU}: Iteration ${__ITER}: Unexpected response while revoking credential: ${r.response}`
          );
        }
        log.debug(`Revoked: Wallet Index: ${walletIndex}, Issuer Connection ID: ${issuer.issuer_connection_id}`);
        return true;
      },
    });

    // Check if credential is revoked when using auto-publish
    const checkRevokedCredentialResponse = checkRevoked(
      issuer.issuer_access_token,
      issuer.credential_exchange_id
    );
    check(checkRevokedCredentialResponse, {
      "Credential state is revoked": (r) => {
        if (r.status !== 200) {
          throw new Error(
            `VU ${__VU}: Iteration ${__ITER}: Unexpected response while checking if credential is revoked: ${r.status}`
          );
        }
        const responseBody = JSON.parse(r.body);
        if (responseBody.state !== "revoked") {
          throw new Error(
            `VU ${__VU}: Iteration ${__ITER}: Credential state is not revoked. Current state: ${responseBody.state}`
          );
        }
        return true;
      },
    });
  } else {
    // Option B: Only revoke (no publish, no check)
    // log.debug(`Revoking credential without auto-publish.`);
    revokeCredentialResponse = revokeCredential(
      issuer.issuer_access_token,
      issuer.credential_exchange_id
    );
    check(revokeCredentialResponse, {
      "Credential revoked successfully": (r) => {
        if (r.status !== 200) {
          throw new Error(
            `VU ${__VU}: Iteration ${__ITER}: Unexpected response while revoking credential: ${r.response}`
          );
        }
        return true;
      },
    });
  }

  sleep(sleepDuration);
  testFunctionReqs.add(1);
}
