# acapy-cloud Helm Chart

This Helm chart deploys a complete stack of ACA-Py related components for managing decentralized
identities and verifiable credentials.

## Overview

This is a generic Helm chart that can deploy any of the following components:

- endorser
- governance-agent
- governance-web
- ledger-browser
- ledger-nodes
- multitenant-agent
- multitenant-web
- public-web
- tails-server
- tenant-web
- trust-registry
- waypoint

Each component can be deployed by using the appropriate values file configuration.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- PV provisioner support in the underlying infrastructure (for components requiring persistence)
- NGINX Ingress Controller (for ingress support)

## Installation

To install the chart from the local repository:

```bash
# Clone the repository
git clone https://github.com/didx-xyz/acapy-cloud.git
cd acapy-cloud/helm/acapy-cloud

# Install a specific component
helm install my-release . -f ./conf/local/<component>.yaml
```

Replace `<component>` with one of the available components (e.g., `endorser`, `governance-agent`, etc.)

### Note about Redpanda Connect

acapy-cloud uses Redpanda Connect for event processing. The pipelines are defined in the
[connect-processors](../../resources/connect-processors) directory.

Before installing Redpanda Connect, you will need to manually create therequired config maps:
-  Config Map with the processor pipelines:
  ```bash
  kubectl create configmap connect-cloud-pipelines \
    --from-file=resources/connect-processors/cloud/pipelines
  ```
-  Config Map with the processor resources:
  ```bash
  kubectl create configmap connect-cloud-resources \
    --from-file=resources/connect-processors/cloud/resources
  ```

Refer to [`acapy-cloud.yaml.gotmpl`](../acapy-cloud.yaml.gotmpl) and
[`connect-cloud.yaml`](./conf/local/connect-cloud.yaml) for an example on installing/configuring Redpanda Connect.

## Configuration

### Common Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas for the deployment | `1` |
| `image.registry` | Container image registry | `ghcr.io/didx-xyz` |
| `image.pullPolicy` | Container image pull policy | `Always` |
| `image.tag` | Container image tag | `latest` |
| `serviceAccount.create` | Create service account | `true` |
| `serviceAccount.automount` | Automount service account token | `false` |
| `ingressDomain` | Base domain for ingress hosts | `cloudapi.127.0.0.1.nip.io` |
| `ingress` | Ingress configuration | `{}` |
| `ingress.*.enabled` | Enable ingress | `false` |
| `ingress.*.className` | Ingress class | `nginx` |
| `ingress.*.rules` | Ingress host and path rules | `[]` |
| `ingress.*.annotations` | Annotations for ingress | `{}` |
| `persistence.enabled` | Enable persistence | `false` |
| `autoscaling.enabled` | Enable autoscaling | `false` |

### Ingress Configuration Example

```yaml
ingressDomain: cloudapi.127.0.0.1.nip.io
ingress:
  internal:
    enabled: true
    className: nginx
    rules:
      - host: public-web.{{ .Values.ingressDomain }}
        paths:
          - path: /public
  cloudapi-internal:
    enabled: true
    className: nginx
    annotations:
      nginx.ingress.kubernetes.io/cors-allow-headers: x-api-key
      nginx.ingress.kubernetes.io/enable-cors: "true"
    rules:
      - host: '{{ .Values.ingressDomain }}'
        paths:
          - path: /public
```

### Component-Specific Parameters

Each component has its own set of specific parameters defined in their respective values files in the `conf/local` directory:

- [`endorser.yaml`](./conf/local/endorser.yaml)
- [`governance-agent.yaml`](./conf/local/governance-agent.yaml)
- [`governance-web.yaml`](./conf/local/governance-web.yaml)
- [`ledger-browser.yaml`](./conf/local/ledger-browser.yaml)
- [`mediator.yaml`](./conf/local/mediator.yaml)
- [`multitenant-agent.yaml`](./conf/local/multitenant-agent.yaml)
- [`multitenant-web.yaml`](./conf/local/multitenant-web.yaml)
- [`public-web.yaml`](./conf/local/public-web.yaml)
- [`tails-server.yaml`](./conf/local/tails-server.yaml)
- [`tenant-web.yaml`](./conf/local/tenant-web.yaml)
- [`trust-registry.yaml`](./conf/local/trust-registry.yaml)
- [`waypoint.yaml`](./conf/local/waypoint.yaml)

## Architecture

The chart deploys several interconnected components:

- **Governance Agent**: Manages the overall governance of the system (endorsing transactions and creating credential schemas)
- **Multitenant Agent**: Manages all tenant operations
- **Endorser**: Manages endorsement of ledger operations
- **Ledger Browser**: Provides a web interface for ledger exploration
- **Trust Registry**: Maintains the trust framework
- **Tails Server**: Manages revocation tails files
- **Web Interfaces**: Various web UIs for different purposes (governance, tenant, public)

## Persistence

The chart supports persistence for components that require it (e.g., `tails-server`, `multitenant-agent`).
Configure persistence options in the respective values files.

## Security

The chart includes several security features:

- Service account creation and configuration
- Pod security contexts
- Secret management for sensitive data
- Ingress configurations with optional TLS
- Istio service mesh integration (optional)

## Monitoring & Logging

The chart includes:

- Datadog integration for monitoring
- Configurable log formats and levels
- Health check probes
- Resource monitoring and management

## Development

For local development:

1. Clone the repository
2. Modify the values files as needed
3. Install using Helm:

```bash
helm install my-release . -f ./conf/local/<component>.yaml
```

## Additional Notes

- The chart uses rolling updates by default
- Horizontal Pod Autoscaling can be enabled for each component
- Components can be deployed on spot instances using node affinity settings
- Ingress configurations support both internal and external access patterns

## Contributing

Contributions are welcome! Please read the contributing guidelines in the repository.

## License

This chart is part of the acapy-cloud project. See the LICENSE file for details.
