/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { bootstrapIssuer } from "../libs/setup.js";
import file from "k6/x/file";
import { log } from "../libs/k6Functions.js";
import { config } from "../libs/config.js";

const issuerPrefix = config.test.issuerPrefix;
const schemaName = config.schema.name;
const schemaVersion = config.schema.version;
const numIssuers = config.test.numIssuers;
const holderPrefix = config.test.holderPrefix;
const outputPrefix = `${issuerPrefix}`;

const filepath = `output/${outputPrefix}-create-issuers.jsonl`;
export function setup() {
  file.writeString(filepath, "");
}

export default function () {
  const walletName = issuerPrefix;
  const credDefTag = walletName;
  log.info(`Number of Issuers: ${numIssuers}`);
  const issuers = bootstrapIssuer(
    numIssuers,
    issuerPrefix,
    credDefTag,
    schemaName,
    schemaVersion
  );
  issuers.forEach((issuerData) => {
    file.appendString(filepath, `${JSON.stringify(issuerData)}\n`);
    log.debug(`Issuer: ${JSON.stringify(issuerData)}`);
    log.debug(`Wallet ID: ${issuerData.walletId}`);
    log.debug(`Credential Definition ID: ${issuerData.credentialDefinitionId}`);
  });

  return issuers;
}
