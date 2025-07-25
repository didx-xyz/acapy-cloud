/* global __ENV, __ITER, __VU, console */
/* eslint-disable no-undefined, no-console, camelcase */

import { config } from './config.js';

/**
 * K6 Logging Utility
 *
 * Provides structured logging for k6 performance tests with automatic VU (Virtual User)
 * and iteration tracking. All log messages are prefixed with [VU:x|Iter:y] for easy
 * identification during test execution.
 *
 * During setup/teardown phases where VU/ITER are not available, only timestamp is shown.
 *
 * Debug logging can be controlled via the DEBUG environment variable:
 * - Set DEBUG=true or DEBUG=1 to enable debug messages
 * - Debug messages are filtered out when DEBUG is not enabled
 *
 * Usage:
 *   import { log } from './libs/k6Functions.js';
 *
 *   log.info('Test started');              // [VU:1|Iter:1] Test started (during test)
 *   log.info('Setup complete');            // Setup complete (during setup/teardown)
 *   log.debug('Debug info', data);         // [VU:1|Iter:1] DEBUG: Debug info {data}
 *   log.error('Something failed');         // [VU:1|Iter:1] Something failed
 *   log.warn('Warning message');          // [VU:1|Iter:1] Warning message
 *
 * Supported methods: debug, info, error, warn
 * Only debug messages include the level name in the output prefix.
 */
const DEBUG_ENABLED = config.debug.enabled;

// Helper function to generate prefix with timestamp
function getLogPrefix(includeLevel = false) {
  const timestamp = new Date().toISOString();

  // Check if VU and ITER are available (they're undefined during setup/teardown)
  let vuInfo = '';
  if (typeof __VU !== 'undefined' && typeof __ITER !== 'undefined') {
    vuInfo = `[VU:${__VU}|Iter:${__ITER}] `;
  }

  const levelSuffix = includeLevel ? ' DEBUG:' : '';
  return `${timestamp} ${vuInfo}${levelSuffix}`.trim();
}

const log = {
  debug(message, ...args) {
    if (!DEBUG_ENABLED) return;
    console.log(`${getLogPrefix(true)} ${message}`, ...args);
  },

  info(message, ...args) {
    console.log(`${getLogPrefix()} ${message}`, ...args);
  },

  warn(message, ...args) {
    console.warn(`${getLogPrefix()} ${message}`, ...args);
  },

  error(message, ...args) {
    console.error(`${getLogPrefix()} ${message}`, ...args);
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
  const shouldShuffle = config.debug.shuffle;

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
