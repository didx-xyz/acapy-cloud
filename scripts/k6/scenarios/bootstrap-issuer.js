/* global __ENV, __ITER, __VU */
/* eslint-disable no-undefined, no-console, camelcase */

import { bootstrapIssuer } from "../libs/setup.js";
import file from "k6/x/file";
import { log } from "../libs/k6Functions.js";

const issuerPrefix = __ENV.ISSUER_PREFIX;
const schemaName = __ENV.SCHEMA_NAME;
const schemaVersion = __ENV.SCHEMA_VERSION;
const numIssuers = __ENV.NUM_ISSUERS;
const holderPrefix = __ENV.HOLDER_PREFIX;
const outputPrefix = `${issuerPrefix}`;

const filepath = `output/${outputPrefix}-create-issuers.json`;
export function setup() {
  file.writeString(filepath, "");
}

export default function () {
  const walletName = issuerPrefix;
  const credDefTag = walletName;
  log('info', `Number of Issuers: ${numIssuers}`);
  const issuers = bootstrapIssuer(
    numIssuers,
    issuerPrefix,
    credDefTag,
    schemaName,
    schemaVersion
  );
  issuers.forEach((issuerData) => {
    file.appendString(filepath, `${JSON.stringify(issuerData)}\n`);
    log('debug', `Issuer: ${JSON.stringify(issuerData)}`);
    log('debug',`Wallet ID: ${issuerData.walletId}`);
    log('debug', `Credential Definition ID: ${issuerData.credentialDefinitionId}`);
  });

  return issuers;
}
