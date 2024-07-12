# aries-cloudapi-python

[![Codacy Badge](https://app.codacy.com/project/badge/Grade/ceca5ac566f74a3a8bfb3095074117ad)](https://www.codacy.com/gh/didx-xyz/aries-cloudapi-python/dashboard?utm_source=github.com&utm_medium=referral&utm_content=didx-xyz/aries-cloudapi-python&utm_campaign=Badge_Grade)
[![Codacy Badge](https://app.codacy.com/project/badge/Coverage/ceca5ac566f74a3a8bfb3095074117ad)](https://www.codacy.com/gh/didx-xyz/aries-cloudapi-python/dashboard?utm_source=github.com&utm_medium=referral&utm_content=didx-xyz/aries-cloudapi-python&utm_campaign=Badge_Coverage)

:construction: This project is currently under development. Please do not use this in production.

## Overview

This project essentially comprises a [FastAPI](https://fastapi.tiangolo.com/) application built around the [Hyperledger Aries stack](https://github.com/hyperledger/), primarily tailored for [Yoma](https://yoma.africa)-specific use cases. The FastAPI app serves as a wrapper around common workflows, facilitating real-life applications of the stack. It acts as a form of middleware or interface for client applications (e.g., a mobile app) and the backend stack, using [Aries CloudController](https://github.com/didx-xyz/aries-cloudcontroller-python) and [ACA-Py](https://github.com/hyperledger/aries-cloudagent-python). The aim is to streamline a client's workflow by providing convenient API endpoints for common workflows, such as creating wallets, managing connections, credentials, proofs, and workflows. Multiple API calls to the AriesCloudAgent can often be condensed into a single call via this API. For example, creating a wallet, which involves writing to the ledger, awaiting the result, accepting a TAA, creating a DID, and finally creating the wallet itself, can be done in a single call. Convenient, isn't it?

## How to Run It

Running the project is straightforward — it's all containerized. Simply execute `./manage up` from the project root. This command will spin up and provision everything you need. You can then visit [localhost:8100/api/doc](http://localhost:8100/api/doc) to access the Swagger documentation and begin experimenting.

If you're familiar with Make, feel free to check the Makefile for some handy project-running methods.

### Requirements

To run the project, you will need Docker and docker-compose, as well as the ability to run a POSIX shell (e.g., sh or bash).

To install Docker, follow the instructions for your operating system in the [official docs](https://docs.docker.com/engine/install/).

Next, follow the instructions for docker-compose in [their docs](https://docs.docker.com/compose/install/).

If you experience any issues while running the project, feel free to reach out by opening an issue or contacting one of the contributors.

## Docs

You can find more detailed documentation in the [`./docs` folder](docs/README.md). The `Quick Start`, `Common Steps` and `Example Flows` will be most useful.

## Contributing

While this project was primarily developed to meet the needs of [Yoma](https://yoma.africa), it is an open-source project that can be used for other Hyperledger Aries projects as well. We welcome contributions from everyone. Feel free to engage in discussions, create a PR against a ticket, or open an issue yourself, following the GitHub guidelines.

## Running Tests

The tests use `pytest`. For convenience, use GNU Make to run them. First, ensure the project is running locally by executing `make start`. In another shell, you can now run `make tests` to run all tests or `make unit-tests` to run only the unit tests.

Without using `make`, you can run:

```bash
./manage up
```

Install the requirements:

```bash
bash scripts/install_all_dependencies.sh
```

To start the containers and run the tests:

```bash
pytest .
```

Or only the unit tests:

```bash
pytest --ignore=app/tests/e2e
```

You can specify the log level of the pytest output by using the `--log-cli-level` flag.

```bash
pytest . --log-cli-level=DEBUG
```

This will output all log messages with a log level of `DEBUG` or higher.

To run specific tests, you can specify the path to the test file and the test method. For example:

```bash
pytest app/tests/e2e/test_verifier.py::test_accept_proof_request_oob_v1 --log-cli-level=1
```

## Running containerised tests

```bash
./manage up
```

In another terminal:

```bash
./manage up pytest
```

## CI/CD

Please, refer to the [CI/CD docs](./.github/workflows/README.md) for more information.
