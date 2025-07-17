/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check } from "k6";
import { getAuthHeaders } from '../libs/auth.js';
import { createCredentialDefinition } from "../libs/functions.js";
import { createSchemaIfNotExists } from "../libs/schemaUtils.js";
import { config } from "../libs/config.js";

const vus = config.test.vus;
const iterations = config.test.iterations;
const schemaName = config.schema.name;
const schemaVersion = config.schema.version;
const issuerPrefix = config.test.issuerPrefix;

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
    "http_req_duration{scenario:default}": ["max>=0"],
    "http_reqs{scenario:default}": ["count >= 0"],
    "http_reqs{my_custom_tag:specific_function}": ["count>=0"],
    "iteration_duration{scenario:default}": ["max>=0"],
    checks: ["rate==1"],
  },
  tags: {
    test_run_id: "phased-issuance",
    test_phase: "create-creddef",
  },
};

const inputFilepath = `../output/${issuerPrefix}-create-issuers.jsonl`;
const data = open(inputFilepath, "r");

export function setup() {
  const { governanceHeaders } = getAuthHeaders();
  const issuers = data.trim().split("\n").map(JSON.parse);
  const schemaId = createSchemaIfNotExists(
    governanceHeaders,
    schemaName,
    schemaVersion
  );
  check(schemaId, {
    "Schema ID is not null": (id) => id !== null && id !== undefined,
  });
  return { issuers, schemaId }; // eslint-disable-line no-eval
}

const iterationsPerVU = options.scenarios.default.iterations;
// Helper function to calculate the wallet index based on VU and iteration
function getWalletIndex(vu, iter) {
  const walletIndex = (vu - 1) * iterationsPerVU + (iter - 1);
  return walletIndex;
}

export default function (data) {
  const issuers = data.issuers;
  const schemaId = data.schemaId;
  const walletIndex = getWalletIndex(__VU, __ITER + 1); // __ITER starts from 0, adding 1 to align with the logic
  const wallet = issuers[walletIndex];
  const credDefTag = wallet.wallet_name;

  const createCredentialDefinitionResponse = createCredentialDefinition(
    wallet.access_token,
    credDefTag,
    schemaId
  );
  check(createCredentialDefinitionResponse, {
    "Credential definition created successfully": (r) => r.status === 200,
  });
}
