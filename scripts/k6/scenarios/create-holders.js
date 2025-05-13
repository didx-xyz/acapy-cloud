/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check, sleep } from "k6";
import { SharedArray } from "k6/data";
import { Counter, Trend } from "k6/metrics";
import file from "k6/x/file";
import { getAuthHeaders } from '../libs/auth.js';
import { createTenant } from "../libs/functions.js";

const vus = Number(__ENV.VUS || 1);
const iterations = Number(__ENV.ITERATIONS || 1);
const holderPrefix = __ENV.HOLDER_PREFIX || "holder";
const issuerPrefix = __ENV.ISSUER_PREFIX || "issuer";
const sleepDuration = Number(__ENV.SLEEP_DURATION || 0);
const outputPrefix = `${holderPrefix}`;
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
  setupTimeout: "300s", // Increase the setup timeout to 120 seconds
  teardownTimeout: "120s", // Increase the teardown timeout to 120 seconds
  maxRedirects: 4,
  thresholds: {
    // https://community.grafana.com/t/ignore-http-calls-made-in-setup-or-teardown-in-results/97260/2
    // "http_req_duration{scenario:default}": ["max>=0"],
    // "http_reqs{scenario:default}": ["count >= 0"],
    // "iteration_duration{scenario:default}": ["max>=0"],
    checks: ["rate==1"],
    // 'specific_function_reqs{my_custom_tag:specific_function}': ['count>=0'],
    // 'specific_function_reqs{scenario:default}': ['count>=0'],
    'test_function_reqs{my_custom_tag:specific_function}': ['count>=0'],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "create-holders",
    version: `${version}`,
  },
};

// const specificFunctionReqs = new Counter('specific_function_reqs');
const testFunctionReqs = new Counter("test_function_reqs");
// const mainIterationDuration = new Trend("main_iteration_duration");

// Seed data: Generating a list of options.iterations unique wallet names
const wallets = new SharedArray("wallets", () => {
  const walletsArray = [];
  for (
    let i = 0;
    i < options.scenarios.default.iterations * options.scenarios.default.vus;
    i++
  ) {
    walletsArray.push({
      wallet_label: `${holderPrefix} ${i}`,
      wallet_name: `${holderPrefix}_${i}`,
    });
  }
  return walletsArray;
});

const filepath = `output/${outputPrefix}-create-holders.json`;
export function setup() {
  file.writeString(filepath, "");

  const { tenantAdminHeaders } = getAuthHeaders();
  return { tenantAdminHeaders };
}

const iterationsPerVU = options.scenarios.default.iterations;
// Helper function to calculate the wallet index based on VU and iteration
function getWalletIndex(vu, iter) {
  const walletIndex = (vu - 1) * iterationsPerVU + (iter - 1);
  return walletIndex;
}

export default function (data) {
  const start = Date.now();
  const tenantAdminHeaders = data.tenantAdminHeaders;
  const walletIndex = getWalletIndex(__VU, __ITER + 1); // __ITER starts from 0, adding 1 to align with the logic
  const wallet = wallets[walletIndex];

  const createTenantResponse = createTenant(tenantAdminHeaders, wallet);
  check(createTenantResponse, {
    "Create Tenant Response status code is 200": (r) => {
      if (r.status !== 200) {
        throw new Error(`Unexpected response status: ${r.status}`);
      }
      return true;
    },
  });
  const { wallet_id: walletId, access_token: holderAccessToken } = JSON.parse(
    createTenantResponse.body
  );

  // specificFunctionReqs.add(1, { my_custom_tag: 'specific_function' });

  const holderData = JSON.stringify({
    wallet_label: wallet.wallet_label,
    wallet_name: wallet.wallet_name,
    wallet_id: walletId,
    access_token: holderAccessToken,
  });
  file.appendString(filepath, `${holderData}\n`);

  const end = Date.now();
  const duration = end - start;
  // console.log(`Duration for iteration ${__ITER}: ${duration} ms`);
  // mainIterationDuration.add(duration);
  sleep(sleepDuration);
  testFunctionReqs.add(1);
}
