/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check } from "k6";
import { SharedArray } from "k6/data";
import { Counter } from "k6/metrics";
import { getAuthHeaders } from '../libs/auth.js';
import { deleteTenant, getWalletIdByWalletName, getWalletIndex } from "../libs/functions.js";
import file from "k6/x/file"; // Add file import

const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const issuerPrefix = __ENV.ISSUER_PREFIX;
const outputPrefix = `${issuerPrefix}`;

export const options = {
  scenarios: {
    default: {
      executor: "per-vu-iterations",
      vus,
      iterations,
      maxDuration: "120s",
    },
  },
  setupTimeout: "180s", // Increase the setup timeout to 120 seconds
  teardownTimeout: "120s", // Increase the teardown timeout to 120 seconds
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
    test_phase: "delete-holders",
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

const filepath = `output/${outputPrefix}-create-issuers.json`;

export function setup() {
  const { tenantAdminHeaders } = getAuthHeaders();
  return { tenantAdminHeaders }; // eslint-disable-line no-eval
}

export function teardown() {
  try {
    file.deleteFile(filepath);
    console.log(`Successfully deleted file: ${filepath}`);
  } catch (error) {
    console.error(`Error deleting file ${filepath}: ${error}`);
  }
}

export default function (data) {
  const tenantAdminHeaders = data.tenantAdminHeaders;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations);
  const wallet = wallets[walletIndex];

  const walletId = getWalletIdByWalletName(tenantAdminHeaders, wallet.wallet_name);
  const deleteHolderResponse = deleteTenant(tenantAdminHeaders, walletId);
  check(deleteHolderResponse, {
    "Delete Issuer Tenant Response status code is 204": (r) => {
      if (r.status !== 204 && r.status !== 200) {
        console.error(
          `Unexpected response status while deleting issuer tenant ${walletId}: ${r.status}`
        );
        return false;
      }
      // console.log(`Deleted holder tenant ${walletId} successfully.`);
      return true;
    },
  });
  testFunctionReqs.add(1);
}
