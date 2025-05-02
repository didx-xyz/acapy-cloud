# acapy-cloud

![Python](https://img.shields.io/badge/python-3.13-blue.svg)
[![Toolset: Mise](https://img.shields.io/badge/toolset-Mise-orange.svg?style=flat)](https://mise.jdx.dev/)
[![Dev Experience: Tilt](https://img.shields.io/badge/devex-Tilt-blue.svg?style=flat)](https://tilt.dev)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/ceca5ac566f74a3a8bfb3095074117ad)](https://app.codacy.com/gh/didx-xyz/acapy-cloud/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![Codacy Badge](https://app.codacy.com/project/badge/Coverage/ceca5ac566f74a3a8bfb3095074117ad)](https://app.codacy.com/gh/didx-xyz/acapy-cloud/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_coverage)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/didx-xyz/acapy-cloud/badge)](https://scorecard.dev/viewer/?uri=github.com/didx-xyz/acapy-cloud)

🚧 This project is currently under development. If you would like to use this in
production, please [contact us](mailto:info@didx.co.za) first to discuss your use case.

✅ You should be able to deploy this project in a local environment using the
[Quick Start Guide](./docs/src/Quick%20Start%20Guide.md)

## Overview

This project comprises a [FastAPI](https://fastapi.tiangolo.com/) application built
around [ACA-Py](https://github.com/openwallet-foundation/acapy),
primarily tailored for [Yoma](https://yoma.world)-specific use cases.

The main [app](app) provides an API interface
that simplifies complex self-sovereign identity (SSI) workflows. Using our
[ACA-Py controller](https://github.com/didx-xyz/aries-cloudcontroller-python), it
provides a streamlined layer of abstraction for client applications (e.g., a
mobile app) to interact within an SSI ecosystem.

What would normally require multiple calls to ACA-Py can be condensed into a single call
through this API. For example, onboarding an issuer — which involves creating a wallet,
establishing a connection with an endorser, generating a public DID, accepting the
Transaction Author Agreement (TAA), publishing the DID to the ledger, and awaiting
confirmation — can all be achieved with a single API call. Convenient, isn't it?

We simplify several key capabilities, including:

- Creating and managing wallets
- Onboarding issuers and verifiers
- Managing connections between parties
- Creating schemas and credential definitions
- Issuing verifiable credentials and handling revocations
- Requesting and validating proofs

To enable this, the project includes essential supporting services:

- An [Endorser](endorser) agent and service for authorizing ledger transactions
- A [Trust Registry](trustregistry) implementation for authorizing valid issuers, verifiers,
  and approved credential schemas
- A webhooks service ([Waypoint](waypoint)) for real-time, server-sent event
  (SSE) notifications and updates

For detailed documentation, please refer to the [docs folder](docs/src/README.md). We recommend:

- [Quick Start Guide](docs/src/Quick%20Start%20Guide.md) - Get up and running quickly
- [Main Documentation](docs/src/README.md) - Detail on the different services, roles, authentication, and further reading
- [Common Steps](docs/src/Common%20Steps.md) - Quick steps for creating tenants, issuing credentials, and requesting proofs
- [Example Flows](docs/src/Example%20Flows.md) - More involved, step-by-step examples

## How to Run It

> [!NOTE]
> For local development we now use Tilt and Kind instead of Docker Compose.
> Legacy Docker Compose files are still available, but deprecated and will be
> removed in the future.

Running the project is straightforward — it's all containerized. Simply execute
`mise run tilt:up` from the project root. This command will spin up a Kind
cluster, build all the necessary docker images, and start the project.
You can then visit [localhost:10350](http://localhost:10350) to access the Tilt
UI.

For detailed setup instructions and requirements, see the [Quick Start Guide](docs/src/Quick%20Start%20Guide.md).

## Running Tests

The tests use `pytest`. For convenience, use Mise to run them. First, ensure
the project is running locally by executing `mise run tilt:up`. In another shell,
you can now run `mise run tests` to run all tests or `mise run tests:unit` to run
only the unit tests.

```bash
mise run tilt:up
```

Install the requirements:

```bash
mise run poetry:install
```

To run the tests you need to set up some environment variables to point Pytest
at the correct endpoints.

```bash
cp .env.example .env
source .env
```

Then you can run the tests:

```bash
poetry run pytest .
```

Or only the unit tests:

```bash
poetry run pytest --ignore=app/tests/e2e
```

You can specify the log level of the pytest output by using the `--log-cli-level`
flag.

```bash
poetry run pytest . --log-cli-level=DEBUG
```

This will output all log messages with a log level of `DEBUG` or higher.

To run specific tests, you can specify the path to the test file and the test
method. For example:

```bash
poetry run pytest \
  app/tests/e2e/test_verifier_oob.py::test_accept_proof_request_oob \
  --log-cli-level=1
```

## Running containerised tests

```bash
mise run tilt:up
```

In another terminal:

```bash
# Run e2e tests
helm upgrade --install acapy-test \
  -f ./helm/acapy-test/conf/local/values.yaml \
  ./helm/acapy-test

# Bootstrap regression tests
helm upgrade --install acapy-regression-test \
  -f ./helm/acapy-test/conf/local/values.yaml \
  -f ./helm/acapy-test/conf/local/regression.yaml \
  --set env.FAIL_ON_RECREATING_FIXTURES=false \
  ./helm/acapy-test

# Run regression tests
helm upgrade --install acapy-regression-test \
  -f ./helm/acapy-test/conf/local/values.yaml \
  -f ./helm/acapy-test/conf/local/regression.yaml \
  --set env.FAIL_ON_RECREATING_FIXTURES=true \
  ./helm/acapy-test
```

## CI/CD

Please, refer to the [CI/CD docs](./.github/workflows/README.md) for more
information.

## Contributing

[![Contributions](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](./CONTRIBUTING.md)

While this project was primarily developed to meet the needs of
[Yoma](https://yoma.world), it is an open-source project that can be used for
other Hyperledger Aries projects as well. We welcome contributions from
everyone. Feel free to engage in discussions, create pull requests against
existing tickets, or open new issues following the GitHub guidelines.
