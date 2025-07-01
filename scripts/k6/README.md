# K6 Load Testing Scripts

⚠️ Disclaimer: This is a work in progress. Refactoring and standardisation
pending... ⚠️

Initial load testing scripts and GH Actions pipeline config to run K6 in
parallel with K8s Pytests.

- Initial K6 flows:
  - setup function to create schema, issuer and cred def
  - create holders
  - establish connections
  - issue credentials
  - proof requests

## Running K6 Scripts

Run with docker compose

### Basic Usage (No Metrics)

By default, the K6 framework runs without DataDog metrics collection:

```sh
# Default behavior - no StatsD dependency, no DataDog container
docker compose up
```

### With DataDog Metrics

To enable StatsD metrics collection with DataDog use the metrics compose file:

```sh
# Enable StatsD metrics + DataDog container
docker compose -f compose.yaml -f compose.metrics.yaml up
```

It is recommended to start DataDog in a separate window to keep the logs specific to K6 clean:

```sh
# Start DataDog container separately
docker compose -f compose.metrics.yaml up datadog
# Start K6 in another terminal
docker compose -f compose.metrics.yaml up xk6
```

This approach automatically:
- Starts the DataDog container with health checks
- Enables StatsD metrics in K6 (`ENABLE_STATSD=true`)
- Configures proper service dependencies
- Waits for DataDog to be healthy before starting K6

The multiple compose files approach ensures clean separation and avoids dependency validation issues.

### Environment Variables

Key configuration options:

- `ENABLE_STATSD`: Enable/disable DataDog StatsD metrics (default: `false`)
- `K6_STATSD_ADDR`: DataDog StatsD address (default: `datadog:8125` when enabled)
- `K6_STATSD_PUSH_INTERVAL`: Metrics push interval in seconds (default: `5`)

## Running Biome to lint/format code

```sh
# Use mise to install Node
mise install

# Use npm to install Biome - `ci` for frozen lockfile
npm ci

# check formatting but don't actually write anything
npm run format:check

# format code
npm run format

# check linting but don't try to auto-fix
npm run lint

# lint and auto-fix if possible
npm run lint:fix
```
