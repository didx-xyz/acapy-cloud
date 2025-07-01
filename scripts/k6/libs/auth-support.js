/* global __ENV */
/* eslint-disable no-undefined, no-console, camelcase */

// Dummy implementations for open-source usage
// Real implementations are in the enterprise repo and conditionally mounted

export function getOrgId() {
  console.log("Using dummy org ID for non-enterprise mode");
  return "dummy-org-id";
}

export function fetchClientSecret() {
  console.log("Using dummy client secret for non-enterprise mode");
  return "dummy-client-secret";
}

export function fetchGovernanceSecret() {
  console.log("Using dummy governance secret for non-enterprise mode");
  return "dummy-governance-secret";
}
