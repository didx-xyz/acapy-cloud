// schemaUtils.js

import { createSchema, getSchema } from "./functions.js";
import { log } from "./k6Functions.js";

export function createSchemaIfNotExists(
  governanceHeaders,
  schemaName,
  schemaVersion
) {
  const schemaExists = checkSchemaExists(
    governanceHeaders,
    schemaName,
    schemaVersion
  );
  if (schemaExists) {
    console.log(
      `Schema: ${schemaName} version: ${schemaVersion} already exists`
    );
    return getSchemaId(governanceHeaders, schemaName, schemaVersion);
  }
  log.info(`Schema: ${schemaName} version: ${schemaVersion} does not exist - creating...`);
  const createSchemaResponse = createSchema(
    governanceHeaders,
    schemaName,
    schemaVersion
  );
  if (createSchemaResponse.status === 200) {
    // Schema created successfully
    const schemaData = JSON.parse(createSchemaResponse.body);
    return schemaData.id;
  }
  // Schema creation failed
  console.error(`Failed to create schema ${schemaName} v${schemaVersion}`);
  throw new Error(`Failed to create schema ${schemaName} v${schemaVersion}`);
}

function checkSchemaExists(governanceHeaders, schemaName, schemaVersion) {
  const getSchemaResponse = getSchema(governanceHeaders, schemaName, schemaVersion);
  if (getSchemaResponse.status === 200 && getSchemaResponse.body !== "[]") {
    // Schema exists
    return true;
  }
  // Schema does not exist
  return false;
}

function getSchemaId(governanceHeaders, schemaName, schemaVersion) {
  const getSchemaResponse = getSchema(governanceHeaders, schemaName, schemaVersion);
  if (getSchemaResponse.status === 200 && getSchemaResponse.body !== "[]") {
    // Schema exists
    const schemaData = JSON.parse(getSchemaResponse.body);
    if (schemaData.length > 0) {
      const schemaId = schemaData[0].id;
      return schemaId;
    }
    console.error("Schema data array is empty");
    return null;
  }
  // Schema does not exist
  console.error("Schema does not exist or request failed");
  return null;
}
