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

Configure local environment variables:

```sh
cp env.local .env.local
```

### Basic Usage (No Metrics)

By default, the K6 framework runs without DataDog metrics collection for faster local development:

```sh
# Default behavior - no StatsD dependency, no DataDog container
docker compose up
```

### With DataDog Metrics

To enable StatsD metrics collection with DataDog (recommended for production/CI), use the `metrics` profile:

```sh
# Enable StatsD metrics + DataDog container
docker compose --profile metrics up
```

This approach automatically:
- Starts the DataDog container with health checks
- Enables StatsD metrics in K6 (`ENABLE_STATSD=true`)
- Configures proper service dependencies

### Advanced Usage

For manual control over the StatsD toggle without profiles:

```sh
# Explicitly disable metrics (same as default)
ENABLE_STATSD=false docker compose up

# Enable metrics without profile (requires manual DataDog setup)
ENABLE_STATSD=true docker compose up xk6
```

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
