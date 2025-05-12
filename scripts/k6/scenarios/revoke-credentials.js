/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import { Counter } from "k6/metrics";
import {
  checkRevoked,
  getWalletIndex,
  revokeCredentialAutoPublish,
} from "../libs/functions.js";

const holderPrefix = __ENV.HOLDER_PREFIX;
const issuerPrefix = __ENV.ISSUER_PREFIX;
const outputPrefix = `${issuerPrefix}-${holderPrefix}`;

const inputFilepath = `../output/${outputPrefix}-create-credentials.json`;
const data = open(inputFilepath, "r");

const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const testFunctionReqs = new Counter("test_function_reqs");
const sleepDuration = Number.parseInt(__ENV.SLEEP_DURATION, 0);

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
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "revoke-credentials",
  },
};

export function setup() {
  const tenants = data.trim().split("\n").map(JSON.parse);
  return { tenants }; // eslint-disable-line no-eval
}

export default function (data) {
  const tenants = data.tenants;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);
  const wallet = tenants[walletIndex];

  const revokeCredentialResponse = revokeCredentialAutoPublish(
    wallet.issuer_access_token,
    wallet.credential_exchange_id
  );
  check(revokeCredentialResponse, {
    "Credential revoked successfully": (r) => {
      if (r.status !== 200) {
        throw new Error(
          `Unexpected response while revoking credential: ${r.response}`
        );
      }
      return true;
    },
  });
  const checkRevokedCredentialResponse = checkRevoked(
    wallet.issuer_access_token,
    wallet.credential_exchange_id
  );
  check(checkRevokedCredentialResponse, {
    "Credential state is revoked": (r) => {
      if (r.status !== 200) {
        throw new Error(
          `Unexpected response while checking if credential is revoked: ${r.status}`
        );
      }
      const responseBody = JSON.parse(r.body);
      if (responseBody.state !== "revoked") {
        throw new Error(
          `Credential state is not revoked. Current state: ${responseBody.state}`
        );
      }
      return true;
    },
  });
  sleep(sleepDuration);
  testFunctionReqs.add(1);
}
