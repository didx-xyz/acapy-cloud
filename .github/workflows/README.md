# CI/CD

The CI/CD pipeline is defined in the [cicd.yml](cicd.yml) file.

```mermaid
---
title: CI/CD Pipeline
---
flowchart LR
    ExportVersions(Export tool versions)
    Lint(Lint / Format)
    TestsUnit(Tests / Unit)
    DockerBuild(Docker / Build)
    DockerPush(Docker / Push)
    TestsLocal(Tests / Local)
    EKSDeploy(EKS / Deploy)
    EKSTestE2E(EKS / Tests / End-to-End)
    EKSTestK6(EKS / Tests / K6)
    Notify(Notify / didx-cloud)
    OpenAPI(OpenAPI / Diff)

    ExportVersions --> Lint
    ExportVersions --> TestsUnit
    Lint --> DockerBuild
    TestsUnit --> DockerBuild
    DockerBuild --> DockerPush
    DockerPush --> TestsLocal
    DockerPush --> EKSDeploy
    DockerPush --> OpenAPI
    EKSDeploy --> EKSTestE2E
    EKSDeploy --> EKSTestK6
    EKSTestE2E --> Notify
    EKSTestK6 --> Notify
    TestsLocal --> Notify
```

Refer to the [helm](../../helm) directory for the Helm charts and Helmfile
configs to deploy acapy-cloud.
