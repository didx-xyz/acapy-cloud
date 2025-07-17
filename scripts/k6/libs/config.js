/* global __ENV */

/**
 * Centralized configuration management for k6 load testing
 * Handles all environment variable parsing, validation, and defaults
 */

class ConfigurationError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ConfigurationError';
  }
}

class Config {
  constructor() {
    this.auth = this._initAuthConfig();
    this.test = this._initTestConfig();
    this.schema = this._initSchemaConfig();
    this.api = this._initApiConfig();
    this.debug = this._initDebugConfig();
  }

  _initAuthConfig() {
    return {
      useEnterprise: this._parseBoolean(__ENV.USE_ENTERPRISE, false),
      tenantAdminApiKey: this._required('TENANT_ADMIN_API_KEY', 'Tenant admin API key is required for authentication'),
      governanceApiKey: this._required('GOVERNANCE_API_KEY', 'Governance API key is required for authentication'),
      clientId: __ENV.CLIENT_ID || null,
      governanceClientId: __ENV.GOVERNANCE_CLIENT_ID || null,
      governanceOauthEndpoint: __ENV.GOVERNANCE_OAUTH_ENDPOINT || null
    };
  }

  _initTestConfig() {
    return {
      vus: this._parseNumber(__ENV.VUS, 4, 'VUS must be a positive number'),
      iterations: this._parseNumber(__ENV.ITERATIONS, 1, 'ITERATIONS must be a positive number'),
      totalBatches: this._parseNumber(__ENV.TOTAL_BATCHES, 1, 'TOTAL_BATCHES must be a positive number'),
      issuerPrefix: __ENV.ISSUER_PREFIX || 'issuer',
      holderPrefix: __ENV.HOLDER_PREFIX || 'holder',
      sleepDuration: this._parseNumber(__ENV.SLEEP_DURATION, 0, 'SLEEP_DURATION must be a non-negative number'),
      version: __ENV.VERSION || '0.1.0',
      numIssuers: this._parseNumber(__ENV.NUM_ISSUERS, 1, 'NUM_ISSUERS must be a positive number'),
      isRevoked: this._parseBoolean(__ENV.IS_REVOKED, false)
    };
  }

  _initSchemaConfig() {
    return {
      name: __ENV.SCHEMA_NAME || 'didx_acc',
      version: __ENV.SCHEMA_VERSION || '0.1.0',
      prefix: __ENV.SCHEMA_PREFIX || 'schema'
    };
  }

  _initApiConfig() {
    return {
      cloudApiUrl: __ENV.CLOUDAPI_URL || 'http://cloudapi.127.0.0.1.nip.io',
      oobInvitation: this._parseBoolean(__ENV.OOB_INVITATION, true),
      useAutoPublish: this._parseBoolean(__ENV.USE_AUTO_PUBLISH, false),
      fireAndForgetRevocation: this._parseBoolean(__ENV.FIRE_AND_FORGET_REVOCATION, false)
    };
  }

  _initDebugConfig() {
    return {
      enabled: this._parseBoolean(__ENV.DEBUG, false),
      shuffle: this._parseBoolean(__ENV.SHUFFLE, false)
    };
  }

  // Utility methods for parsing and validation
  _required(key, message = null) {
    const value = __ENV[key];
    if (!value) {
      const errorMessage = message || `Required environment variable ${key} is missing`;
      throw new ConfigurationError(errorMessage);
    }
    return value;
  }

  _parseNumber(value, defaultValue, errorMessage = null) {
    if (value === undefined || value === null || value === '') {
      return defaultValue;
    }

    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed) || parsed < 0) {
      const message = errorMessage || `Invalid number value: ${value}`;
      throw new ConfigurationError(message);
    }
    return parsed;
  }

  _parseBoolean(value, defaultValue) {
    if (value === undefined || value === null || value === '') {
      return defaultValue;
    }
    return value === 'true' || value === '1';
  }


  // Validation method to check configuration consistency
  validate() {
    const errors = [];

    // Validate enterprise auth requirements
    if (this.auth.useEnterprise) {
      if (!this.auth.clientId) {
        errors.push('CLIENT_ID is required when USE_ENTERPRISE is true');
      }
      if (!this.auth.governanceClientId) {
        errors.push('GOVERNANCE_CLIENT_ID is required when USE_ENTERPRISE is true');
      }
      if (!this.auth.governanceOauthEndpoint) {
        errors.push('GOVERNANCE_OAUTH_ENDPOINT is required when USE_ENTERPRISE is true');
      }
    }

    // Validate test configuration
    if (this.test.vus <= 0) {
      errors.push('VUS must be greater than 0');
    }
    if (this.test.iterations <= 0) {
      errors.push('ITERATIONS must be greater than 0');
    }
    if (this.test.totalBatches <= 0) {
      errors.push('TOTAL_BATCHES must be greater than 0');
    }

    if (errors.length > 0) {
      throw new ConfigurationError(`Configuration validation failed:\n${errors.join('\n')}`);
    }

    return true;
  }

  // Debug method to print configuration (excluding sensitive data)
  printDebug() {
    const debugConfig = {
      auth: {
        useEnterprise: this.auth.useEnterprise,
        tenantAdminApiKey: this.auth.tenantAdminApiKey ? '[REDACTED]' : null,
        governanceApiKey: this.auth.governanceApiKey ? '[REDACTED]' : null,
        clientId: this.auth.clientId
      },
      test: this.test,
      schema: this.schema,
      api: this.api,
      debug: this.debug
    };

    console.log('=== Configuration Debug ===');
    console.log(JSON.stringify(debugConfig, null, 2));
    console.log('=== End Configuration ===');
  }
}

// Export singleton instance
export const config = new Config();
export { ConfigurationError };

// Debug configuration if DEBUG is enabled
if (config.debug.enabled) {
  config.printDebug();
}

// Validate configuration on module load
config.validate();
