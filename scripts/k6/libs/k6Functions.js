/* global __ENV, __ITER, __VU, console */
/* eslint-disable no-undefined, no-console, camelcase */

/**
 * K6 Logging Utility
 *
 * Provides structured logging for k6 performance tests with automatic VU (Virtual User)
 * and iteration tracking. All log messages are prefixed with [VU:x|Iter:y] for easy
 * identification during test execution.
 *
 * Debug logging can be controlled via the DEBUG environment variable:
 * - Set DEBUG=true or DEBUG=1 to enable debug messages
 * - Debug messages are filtered out when DEBUG is not enabled
 *
 * Usage:
 *   import { log } from './libs/k6Functions.js';
 *
 *   log.info('Test started');              // [VU:1|Iter:1] Test started
 *   log.debug('Debug info', data);         // [VU:1|Iter:1] DEBUG: Debug info {data}
 *   log.error('Something failed');         // [VU:1|Iter:1] Something failed
 *   log.warn('Warning message');          // [VU:1|Iter:1] Warning message
 *
 * Supported methods: debug, info, error, warn
 * Only debug messages include the level name in the output prefix.
 */
const DEBUG_ENABLED = __ENV.DEBUG === 'true' || __ENV.DEBUG === '1';

const log = {
  debug(message, ...args) {
    if (!DEBUG_ENABLED) return;
    const prefix = `[VU:${__VU}|Iter:${__ITER}] DEBUG:`;
    console.log(`${prefix} ${message}`, ...args);
  },

  info(message, ...args) {
    const prefix = `[VU:${__VU}|Iter:${__ITER}]`;
    console.log(`${prefix} ${message}`, ...args);
  },

  warn(message, ...args) {
    const prefix = `[VU:${__VU}|Iter:${__ITER}]`;
    console.warn(`${prefix} ${message}`, ...args);
  },

  error(message, ...args) {
    const prefix = `[VU:${__VU}|Iter:${__ITER}]`;
    console.error(`${prefix} ${message}`, ...args);
  }
};

export { log };
