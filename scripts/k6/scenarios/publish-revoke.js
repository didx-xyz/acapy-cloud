/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import { Counter } from "k6/metrics";
import {
  checkRevoked,
  getWalletIndex,
  publishRevocation,
  retry,
  pollAndCheck,
} from "../libs/functions.js";
import { log } from "../libs/k6Functions.js";
import { request } from "k6/http";
import { config } from "../libs/config.js";

const holderPrefix = config.test.holderPrefix;
const issuerPrefix = config.test.issuerPrefix;
const outputPrefix = `${issuerPrefix}-${holderPrefix}`;

const inputFilepath = `../output/${outputPrefix}-create-credentials.jsonl`;
const data = open(inputFilepath, "r");

const vus = config.test.vus;
const iterations = config.test.iterations;
const testFunctionReqs = new Counter("test_function_reqs");
const sleepDuration = config.test.sleepDuration;

const version = config.test.version;

export const options = {
  scenarios: {
    default: {
      executor: "per-vu-iterations",
      vus,
      iterations,
      maxDuration: "24h",
    },
  },
  setupTimeout: "900s",
  teardownTimeout: "180s",
  maxRedirects: 4,
  thresholds: {
    // "http_req_duration{scenario:default}": ["max>=0"],
    // "http_reqs{scenario:default}": ["count >= 0"],
    // "iteration_duration{scenario:default}": ["max>=0"],
    // checks: ["rate==1"],
    checks: ["rate>0.99"],
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

    // log.info(`Sleeping for 5s before publishing revocation...`);
    // sleep(5); // Sleep for 5 seconds before publishing revocation
    log.info(`Publishing revocation for issuer: ${issuerTenant.issuer_wallet_name} (ID: ${issuerTenant.issuer_wallet_id})`);

    let publishRevocationResponse;
    try {
      // Check if we're in fire-and-forget mode from ENV var
      const fireAndForget = config.api.fireAndForgetRevocation;

      // Call the function with the ENV var setting
      publishRevocationResponse = publishRevocation(issuerToken, fireAndForget);

      // Just log the result if needed
      if (fireAndForget) {
        log.info('Publish revocation fired in setup (fire-and-forget mode)');
      } else {
        // Only validate if we're not in fire-and-forget mode
        if (!publishRevocationResponse || publishRevocationResponse.status !== 200) {
          throw new Error('Failed to publish revocation in setup');
        }
        log.info('Publish revocation completed in setup');
      }
    } catch (e) {
      console.error(`Failed after retries: ${e.message}`);
      publishRevocationResponse = e.response || e;
    }

    // Only do the check if NOT fire-and-forget
    if (!config.api.fireAndForgetRevocation) {
      check(publishRevocationResponse, {
        "Revocation published successfully": (r) => {
          if (r.status !== 200) {
            throw new Error(
              `Setup: Unexpected response while publishing revocation: ${r.response}`
            );
          }
          return true;
        }
      });
    }
  }

  log.info(`Published revocations for ${uniqueIssuers.length} issuer(s)`);
  return { tenants };
}

export default function (data) {
  const tenants = data.tenants;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);
  const wallet = tenants[walletIndex];

  // Check if credential is revoked
  let checkRevokedCredentialResponse;
  try {
    checkRevokedCredentialResponse = retry(() => {
      const response = checkRevoked(
        wallet.issuer_access_token,
        wallet.credential_exchange_id
      );
      if (response.status !== 200) {
        throw new Error(`Non-200 status: ${response.status}`);
      }
      return response;
    }, 3, 2000, "checkRevokedCredentialResponse");
  } catch (error) {
    console.error(`Failed after retries: ${error.message}`);
    checkRevokedCredentialResponse = error.response || error;
  }

  // // No point in polling as the events are available immediately.
  // pollAndCheck({
  //   accessToken:  wallet.issuer_access_token,
  //   walletId: wallet.issuer_wallet_id,
  //   topic: "issuer_cred_rev",
  //   field: "cred_ex_id",
  //   fieldId: wallet.credential_exchange_id.substring(3),
  //   state: "revoked",
  //   maxAttempts: 1, // (1+0.5) + (1+1) + (1+2) + (1+3) = 10.5s
  //   lookBack: 60,
  //   requestTimeout: 2,
  //   sseTag: "credential-revoked"
  // }, { perspective: "Issuer" });

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
