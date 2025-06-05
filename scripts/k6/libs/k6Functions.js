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

/**
 * Conditionally shuffles an array based on the SHUFFLE environment variable.
 *
 * @param {Array} array - The array to potentially shuffle
 * @returns {Array} - The original array or shuffled array based on SHUFFLE env var
 *
 * Usage:
 *   Set SHUFFLE=true or SHUFFLE=1 to enable shuffling (default: false)
 *
 *   import { shuffleArray } from './libs/k6Functions.js';
 *   const shuffledData = shuffleArray(originalData);
 */
function shuffleArray(array) {
  const shouldShuffle = __ENV.SHUFFLE === 'true' || __ENV.SHUFFLE === '1';

  if (!shouldShuffle) {
    return array;
  }

  // Create a copy to avoid mutating the original array
  const shuffled = [...array];

  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }

  return shuffled;
}

export { log, shuffleArray };
