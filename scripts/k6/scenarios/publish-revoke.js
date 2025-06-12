/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import { Counter } from "k6/metrics";
import {
  checkRevoked,
  getWalletIndex,
  publishRevocation,
  retry,
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
    test_phase: "publish-revoke",
    version: `${version}`,
  },
};

export function setup() {
  const tenants = data.trim().split("\n").map(JSON.parse);

  // Get unique issuer access tokens to avoid duplicate publishes
  const uniqueIssuers = [
    ...new Set(tenants.map((tenant) => tenant.issuer_access_token)),
  ];

  for (const issuerToken of uniqueIssuers) {
    // Find the tenant data for this issuer token to get wallet info
    const issuerTenant = tenants.find(
      (tenant) => tenant.issuer_access_token === issuerToken
    );

    log.info(`Publishing revocation for issuer: ${issuerTenant.issuer_wallet_name} (ID: ${issuerTenant.issuer_wallet_id})`);

    let publishRevocationResponse;
    try {
      publishRevocationResponse = retry(() => {
        const response = publishRevocation(issuerToken);
        if (response.status !== 200) {
          throw new Error(`publishRevocation Non-200 status: ${response.status} ${response.body}`);
        }
        return response;
      }, 5, 1000, "publishRevocation");
    } catch (e) {
      console.error(`Failed after retries: ${e.message}`);
      publishRevocationResponse = e.response || e;
    }

    check(publishRevocationResponse, {
      "Revocation published successfully": (r) => {
        if (r.status !== 200) {
          throw new Error(
            `Setup: Unexpected response while publishing revocation: ${r.response}`
          );
        }
        return true;
      },
    });
  }

  console.log(`Published revocations for ${uniqueIssuers.length} issuer(s)`);
  return { tenants };
}

export default function (data) {
  const tenants = data.tenants;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);
  const wallet = tenants[walletIndex];

  // Check if credential is revoked
  const checkRevokedCredentialResponse = checkRevoked(
    wallet.issuer_access_token,
    wallet.credential_exchange_id
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

  // sleep(sleepDuration);
  testFunctionReqs.add(1);
}
