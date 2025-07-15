# Quick Start Guide

This guide will walk you through the steps to get acapy-cloud up and running smoothly.

Ensure that you meet the system requirements and have the necessary prerequisites installed.

- [Quick Start Guide](#quick-start-guide)
  - [System Requirements \& Prerequisites](#system-requirements--prerequisites)
  - [Project Setup](#project-setup)
  - [Accessing Services](#accessing-services)
  - [Customization](#customization)
  - [Next Steps](#next-steps)

## System Requirements & Prerequisites

To successfully set up and run the project, your system should meet the following requirements and have the following
prerequisites installed:

### Requirements

- **Memory:** 16GB of RAM
- **CPU:** Intel i5 (minimum 4 cores) or equivalent
- **Disk Space:** Approximately 32GB of free space for Docker images and data

### Prerequisites

- **Operating System:** Linux or macOS (Windows users should use WSL as outlined below)
- **Tools:**
  - Bash
  - Docker
  - Docker Compose
  - Mise

> [!NOTE]
> As of now, **Mise does not support Windows**. Windows users are recommended to use
> [WSL](https://mise.jdx.dev/faq.html#windows-support). If using WSL, additional steps are required for Kind to work
> properly. Refer to the [Kind WSL2 Guide](https://kind.sigs.k8s.io/docs/user/using-wsl2/) for more details.

### Installing Docker

Follow the official Docker installation instructions for your operating system:

- [Docker Engine Installation](https://docs.docker.com/engine/install/)

### Installing Docker Compose

Refer to the official Docker Compose installation guide:

- [Docker Compose Installation](https://docs.docker.com/compose/install/)

### Setting up Mise

[Mise](https://mise.jdx.dev) is used to install and manage development tooling for this project. Choose one of the
following installation methods. We strongly recommend using your system's package manager to install Mise.

```sh
# Homebrew
brew install mise

# Build from source (requires Rust)
cargo install mise

# Arch Linux User Repository
yay -S mise-bin

# Debian/Ubuntu APT (amd64)
sudo apt-get update && sudo apt-get install -y gpg wget curl
sudo install -dm 755 /etc/apt/keyrings
wget -qO - https://mise.jdx.dev/gpg-key.pub | gpg --dearmor | sudo tee /etc/apt/keyrings/mise-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/mise-archive-keyring.gpg arch=amd64] https://mise.jdx.dev/deb stable main" | sudo tee /etc/apt/sources.list.d/mise.list
sudo apt-get update
sudo apt-get install -y mise

# Debian/Ubuntu APT (arm64)
sudo apt-get update && sudo apt-get install -y gpg wget curl
sudo install -dm 755 /etc/apt/keyrings
wget -qO - https://mise.jdx.dev/gpg-key.pub | gpg --dearmor | sudo tee /etc/apt/keyrings/mise-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/mise-archive-keyring.gpg arch=arm64] https://mise.jdx.dev/deb stable main" | sudo tee /etc/apt/sources.list.d/mise.list
sudo apt-get update
sudo apt-get install -y mise
```

For alternative installation methods, visit the [Mise Installation Documentation](https://mise.jdx.dev/getting-started.html#alternate-installation-methods).

#### Activating Mise in Your Shell

After installation, activate Mise by adding the following to your shell configuration:

```sh
# Bash
echo 'eval "$(mise activate bash)"' >> ~/.bashrc && source ~/.bashrc

# Zsh
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc && source ~/.zshrc

# Fish
echo 'mise activate fish | source' >> ~/.config/fish/config.fish && source ~/.config/fish/config.fish
```

Once activated, run the following commands to trust and install all required tools:

```sh
mise trust
mise install
```

For support with other shells, refer to the [Mise Shell Support Documentation](https://mise.jdx.dev/getting-started.html#shells).

## Project Setup

1. **Clone the Repository:**

   ```bash
   git clone --recursive https://github.com/didx-xyz/acapy-cloud
   cd acapy-cloud
   ```

2. **Start the Project:**

   In the root directory of the project, execute:

   ```bash
   mise run tilt:up
   ```

3. **Stop the Project:**

   When you're done, stop the project by running:

   ```bash
   mise run tilt:down
   ```

4. **Destroy the Kind Cluster:**

   To remove the Kind cluster as well:

   ```bash
   mise run tilt:down:destroy
   ```

5. **Clean Slate (Optional):**

   To remove everything, including the Docker cache, execute:

   ```bash
   mise run tilt:down:destroy:all
   ```

## Accessing Services

Once the project is running, access various services via their Swagger interfaces at the following URLs:

- **ACA-Py Governance Agent:** [http://governance-agent.cloudapi.127.0.0.1.nip.io](http://governance-agent.cloudapi.127.0.0.1.nip.io)
- **ACA-Py Multitenant Agent:** [http://multitenant-agent.cloudapi.127.0.0.1.nip.io](http://multitenant-agent.cloudapi.127.0.0.1.nip.io)
- **Governance:** [http://cloudapi.127.0.0.1.nip.io/governance/docs](http://cloudapi.127.0.0.1.nip.io/governance/docs)
- **Multitenant-Admin:** [http://cloudapi.127.0.0.1.nip.io/tenant-admin/docs](http://cloudapi.127.0.0.1.nip.io/tenant-admin/docs)
- **Public:** [http://cloudapi.127.0.0.1.nip.io/public/docs](http://cloudapi.127.0.0.1.nip.io/public/docs)
- **Tenant:** [http://cloudapi.127.0.0.1.nip.io/tenant/docs](http://cloudapi.127.0.0.1.nip.io/tenant/docs)
- **Trust Registry:** [http://trust-registry.cloudapi.127.0.0.1.nip.io/docs](http://trust-registry.cloudapi.127.0.0.1.nip.io/docs)
- **Waypoint:** [http://waypoint.cloudapi.127.0.0.1.nip.io/docs](http://waypoint.cloudapi.127.0.0.1.nip.io/docs)

## Customization

Customize each Docker container's environment parameters by editing its corresponding `.yaml` file
located within the `helm/acapy-cloud/conf/local` directory. For example, to change the `auto-provision` setting for
the ACA-Py multitenant instance from `true` to `false`, modify the `ACAPY_AUTO_PROVISION` value under the `env` section
in `helm/acapy-cloud/conf/local/multitenant-agent.yaml`.
To configure log levels, search for `LOG_LEVEL` and set to your desired level.

## Next Steps

- **[Common Steps](./Common%20Steps.md):** Understand the general capabilities of the project once it's up and running.
- **[Example Flows](./Example%20Flows.md):** Learn how to perform specific SSI flows.
