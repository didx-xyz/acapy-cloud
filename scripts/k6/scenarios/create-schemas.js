/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { check } from "k6";
import { SharedArray } from "k6/data";
import file from "k6/x/file";
import { getAuthHeaders } from "./auth.js";
import { createSchema, getSchema, getWalletIndex } from "../libs/functions.js";
import { config } from "../libs/config.js";

const outputFilepath = "output/create-schemas.jsonl";
const vus = config.test.vus;
const iterations = config.test.iterations;
const schemaPrefix = config.schema.prefix;

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
  const { governanceHeaders } = getAuthHeaders();
  return { governanceHeaders }; // eslint-disable-line no-eval
}

export default function (data) {
  const governanceHeaders = data.governanceHeaders;
  const walletIndex = getWalletIndex(__VU, __ITER, iterations); // __ITER starts from 0, adding 1 to align with the logic
  const schema = schemas[walletIndex];

  const checkSchemaResponse = getSchema(
    governanceHeaders,
    schema.schemaName,
    schema.schemaVersion
  );
  check(checkSchemaResponse, {
    "Schema doesn't exist yet": (r) => r.status === 200 && r.body === "[]",
  });

  const createSchemaResponse = createSchema(
    governanceHeaders,
    schema.schemaName,
    schema.schemaVersion
  );
  check(createSchemaResponse, {
    "Schema created successfully": (r) =>
      r.status === 200 && r.json("id") != null && r.json("id") !== "",
  });

  const getSchemaResponse = getSchema(
    governanceHeaders,
    schema.schemaName,
    schema.schemaVersion
  );

  function isSchemaValid(response) {
    if (response.status !== 200 || response.body === "[]") {
      return false;
    }

    try {
      const schemaData = JSON.parse(response.body);
      return schemaData.length > 0 && schemaData[0].id != null;
    } catch (e) {
      console.error("Failed to parse schema data:", e);
      return false;
    }
  }

  check(getSchemaResponse, {
    "getSchema check passes": (r) => isSchemaValid(r),
  });

  const { id: schemaId } = JSON.parse(getSchemaResponse.body)[0];

  const schemaData = JSON.stringify({
    schema_name: schema.schemaName,
    schema_version: schema.schemaVersion,
    schema_id: schemaId,
  });
  file.appendString(outputFilepath, `${schemaData}\n`);
}
