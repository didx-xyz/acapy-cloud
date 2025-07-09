/* global __ENV, __ITER, __VU */
// Solve Codacy '__ENV' is not defined. error
/* eslint-disable no-undefined, no-console, camelcase */

import { check } from "k6";
import { SharedArray } from "k6/data";
import { Counter, Trend } from "k6/metrics";
import file from "k6/x/file";
import { getAuthHeaders } from '../libs/auth.js';
import {
  createIssuerTenant,
  getTrustRegistryActor,
  getWalletIndex,
} from "../libs/functions.js";

const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const issuerPrefix = __ENV.ISSUER_PREFIX;
const outputPrefix = `${issuerPrefix}`;
// const holderPrefix = __ENV.HOLDER_PREFIX;
const filepath = `output/${outputPrefix}-create-issuers.jsonl`;

export const options = {
  scenarios: {
    default: {
      executor: "per-vu-iterations",
      vus,
      iterations,
      maxDuration: "24h",
    },
  },
  setupTimeout: "300s",
  teardownTimeout: "120s",
  maxRedirects: 4,
  thresholds: {
    // https://community.grafana.com/t/ignore-http-calls-made-in-setup-or-teardown-in-results/97260/2
    checks: ["rate==1"],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "create-issuers",
  },
};

const testFunctionReqs = new Counter("test_function_reqs");

// Seed data: Generating a list of options.iterations unique wallet names
const wallets = new SharedArray("wallets", () => {
  const walletsArray = [];
  for (
    let i = 0;
    i < options.scenarios.default.iterations * options.scenarios.default.vus;
    i++
  ) {
    walletsArray.push({
      wallet_label: `${issuerPrefix} ${i}`,
      wallet_name: `${issuerPrefix}_${i}`,
    });
  }
  return walletsArray;
});

export function setup() {
  const { tenantAdminHeaders } = getAuthHeaders();
  file.writeString(filepath, "");
  return { tenantAdminHeaders };
}

export default function (data) {
  const start = Date.now();
  const tenantAdminHeaders = data.tenantAdminHeaders;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations); // __ITER starts from 0, adding 1 to align with the logic
  const wallet = wallets[walletIndex];
  const credDefTag = wallet.wallet_name;

  const createIssuerTenantResponse = createIssuerTenant(
    tenantAdminHeaders,
    wallet.wallet_name
  );
  check(createIssuerTenantResponse, {
    "Issuer tenant created successfully": (r) => r.status === 200,
  });
  // const issuerAccessToken = createIssuerTenantResponse.json().access_token;
  const { wallet_id: walletId, access_token: accessToken } = JSON.parse(
    createIssuerTenantResponse.body
  );

  const getTrustRegistryActorResponse = getTrustRegistryActor(
    wallet.wallet_name
  );
  check(getTrustRegistryActorResponse, {
    "Trust Registry Actor Response status code is 200": (r) => {
      if (r.status !== 200) {
        console.error(
          `Unexpected response status while getting trust registry actor for issuer tenant ${wallet.wallet_name}: ${r.status}`
        );
        return false;
      }
      // console.log(`Got trust registry actor for issuer tenant ${wallet.wallet_name} successfully.`);
      return true;
    },
  });

  // const createCredentialDefinitionResponse = createCredentialDefinition(bearerToken, issuerAccessToken, credDefTag);
  // check(createCredentialDefinitionResponse, {
  //   "Credential definition created successfully": (r) => r.status === 200
  // });

  const issuerData = JSON.stringify({
    wallet_label: wallet.wallet_label,
    wallet_name: wallet.wallet_name,
    wallet_id: walletId,
    access_token: accessToken,
  });
  file.appendString(filepath, `${issuerData}\n`);

  const end = Date.now();
  const duration = end - start;
  // console.log(`Duration for iteration ${__ITER}: ${duration} ms`);
  // mainIterationDuration.add(duration);
  testFunctionReqs.add(1);
  // sleep(1);
}
