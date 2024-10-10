/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check } from "k6";
import { SharedArray } from "k6/data";
import file from "k6/x/file";
import { getGovernanceBearerToken } from "../libs/auth.js";
import { createSchema, getSchema } from "../libs/functions.js";

const outputFilepath = "output/create-schemas.json";
const vus = Number.parseInt(__ENV.VUS, 10);
const iterations = Number.parseInt(__ENV.ITERATIONS, 10);
const schemaPrefix = __ENV.SCHEMA_PREFIX;

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
    test_phase: "create-schemas",
  },
};

// Seed data: Generating a list of options.iterations unique wallet names
const schemas = new SharedArray("schemas", () => {
  const schemasArray = [];
  for (
    let i = 0;
    i < options.scenarios.default.iterations * options.scenarios.default.vus;
    i++
  ) {
    schemasArray.push({
      schemaName: `${schemaPrefix}_${i}`,
      schemaVersion: `0.0.${i}`,
    });
  }
  return schemasArray;
});

export function setup() {
  file.writeString(outputFilepath, "");
  const governanceBearerToken = getGovernanceBearerToken();
  return { governanceBearerToken }; // eslint-disable-line no-eval
}

const iterationsPerVU = options.scenarios.default.iterations;
// Helper function to calculate the wallet index based on VU and iteration
function getWalletIndex(vu, iter) {
  const walletIndex = (vu - 1) * iterationsPerVU + (iter - 1);
  return walletIndex;
}

export default function (data) {
  const governanceBearerToken = data.governanceBearerToken;
  const walletIndex = getWalletIndex(__VU, __ITER + 1); // __ITER starts from 0, adding 1 to align with the logic
  const schema = schemas[walletIndex];

  const checkSchemaResponse = getSchema(
    governanceBearerToken,
    schema.schemaName,
    schema.schemaVersion
  );
  check(checkSchemaResponse, {
    "Schema doesn't exist yet": (r) => r.status === 200 && r.body === "[]",
  });

  const createSchemaResponse = createSchema(
    governanceBearerToken,
    schema.schemaName,
    schema.schemaVersion
  );
  check(createSchemaResponse, {
    "Schema created successfully": (r) =>
      r.status === 200 && r.json("id") != null && r.json("id") !== "",
  });

  const getSchemaResponse = getSchema(
    governanceBearerToken,
    schema.schemaName,
    schema.schemaVersion
  );
  check(getSchemaResponse, {
    "getSchema check passes": (r) => {
      if (r.status !== 200 || r.body === "[]") {
        return false;
      }

      try {
        const schemaData = JSON.parse(r.body);
        return schemaData.length > 0 && schemaData[0].id != null;
      } catch (e) {
        console.error("Failed to parse schema data:", e);
        return false;
      }
    },
  });

  const { id: schemaId } = JSON.parse(getSchemaResponse.body)[0];

  const schemaData = JSON.stringify({
    schema_name: schema.schemaName,
    schema_version: schema.schemaVersion,
    schema_id: schemaId,
  });
  file.appendString(outputFilepath, `${schemaData}\n`);
}
