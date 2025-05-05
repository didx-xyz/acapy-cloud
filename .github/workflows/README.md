# CI/CD

The CI/CD pipeline is defined in the [cicd.yml](cicd.yml) file.

```mermaid
---
title: CI/CD Pipeline
---
flowchart LR
    ExportVersions(Export tool versions)
    Format(Format Check)
    Unit(Unit Tests)
    Docker(Docker Build/Push)
    Test(Local Tests)
    DeployTest(Deploy and Test EKS)
    Notify(Notify didx-cloud)

    ExportVersions --> Format
    ExportVersions --> Unit
    Format --> Docker
    Unit --> Docker
    Docker --> Test
    Docker --> DeployTest
    DeployTest --> Notify
    Test --> Notify
```

Refer to the [helm](../../helm) directory for the Helm charts and Helmfile
configs to deploy acapy-cloud.
