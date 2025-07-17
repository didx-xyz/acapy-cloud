/* global __ENV, __ITER, __VU */
// Solve Codacy '__ENV' is not defined. error
/* eslint-disable no-undefined, no-console, camelcase */

import { check } from "k6";
import { SharedArray } from "k6/data";
import { Counter, Trend } from "k6/metrics";
import { getBearerToken } from "../libs/auth.js";
import { getDocs } from "../libs/functions.js";
import { config } from "../libs/config.js";

const vus = config.test.vus;
const iterations = config.test.iterations;
const issuerPrefix = config.test.issuerPrefix;
// const holderPrefix = config.test.holderPrefix;

export const options = {
  scenarios: {
    default: {
      executor: "per-vu-iterations",
      vus: vus,
      iterations: iterations,
      maxDuration: "24h",
    },
  },
  setupTimeout: "300s", // Increase the setup timeout to 120 seconds
  teardownTimeout: "120s", // Increase the teardown timeout to 120 seconds
  maxRedirects: 4,
  thresholds: {
    // https://community.grafana.com/t/ignore-http-calls-made-in-setup-or-teardown-in-results/97260/2
    "http_req_duration{scenario:default}": ["max>=0"],
    "http_reqs{scenario:default}": ["count >= 0"],
    "iteration_duration{scenario:default}": ["max>=0"],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "create-issuers",
  },
};

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
      walletLabel: `${issuerPrefix} ${i}`,
      walletName: `${issuerPrefix}_${i}`,
    });
  }
  return walletsArray;
});

export function setup() {
  const bearerToken = getBearerToken();
  return { bearerToken };
}

const iterationsPerVU = options.scenarios.default.iterations;
function getWalletIndex(vu, iter) {
  const walletIndex = (vu - 1) * iterationsPerVU + (iter - 1);
  return walletIndex;
}

export default function (data) {
  const bearerToken = data.bearerToken;
  const getDocsResponse = getDocs();
  check(getDocsResponse, {
    "Docs fetched successfully": (r) => r.status === 200,
  });
}
