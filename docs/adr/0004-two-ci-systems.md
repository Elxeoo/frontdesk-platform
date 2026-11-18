# ADR-0004: GitHub Actions for the application, Azure Pipelines for the infrastructure

- **Status:** Accepted
- **Date:** 2026-11-17
- **Updated:** 2026-11-18 (the Azure Pipelines check is now required)

## Context

The application already has its CI in GitHub Actions: lint, tests, a smoke test, image scans, and signed images
pushed to GHCR. None of these workflows signs in to Azure.

Terraform needs a credential that can change Azure resources, and its changes should wait for a person to read
the plan before they are applied. The question is where that credential and that approval live.

## Decision

Infrastructure runs in Azure Pipelines (`infra/pipelines/terraform.yml`); the application stays in GitHub Actions.

- The only Azure credential is the `sc-azure-frontdesk` service connection in Azure DevOps. It uses workload
  identity federation with the `id-frontdesk-pipeline` managed identity, so no secret is stored anywhere.
  GitHub Actions has no Azure access.
- Validate and Plan run on pull requests that touch `infra/` and on `main`. Apply runs only on `main`, as a
  deployment job on the `dev` environment, which has a manual approval check. It applies the plan file that the
  Plan stage published.
- The `Elxeoo.frontdesk-platform` check is required on `main`. When the path filter skips a pull request,
  Azure Pipelines still reports this check as neutral, and GitHub counts neutral as passing, so application-only
  pull requests are not blocked. The stage checks (`Validate validate`, `Plan plan`) are not required: they only
  appear when the pipeline actually runs.

GitHub Actions could also gate a deployment with environment reviewers, so approval alone does not decide this.
The deciding point is separation: the system that builds application code never holds the key to Azure.

## Consequences

**Positive**

- A mistake or a compromised workflow on the application side cannot change Azure resources.
- Infrastructure changes have their own path: checks, a saved plan, and a human approval.
- A pull request whose validation or plan fails cannot be merged.

**Negative**

- Two CI systems to maintain, each with its own permissions, logs and settings.
- If Azure Pipelines does not report at all, every pull request waits on the required check. The ruleset has
  no bypass, so during an outage the check has to be removed from the ruleset and added back afterwards.
- The free tier gives one Microsoft-hosted parallel job, so runs queue behind each other.
- Microsoft-hosted agents have no fixed IP, so the state storage account keeps a public endpoint. Trivy finding
  AZU-0012 is accepted inline in `infra/terraform/bootstrap/main.tf` until a private endpoint and an agent inside
  the VNet exist.

## Alternatives considered

- **Everything in GitHub Actions**, with OIDC to Azure and environment reviewers. Rejected: one system would hold
  both the application build and the Azure credential, so one compromised workflow could reach both.
- **Everything in Azure Pipelines.** Rejected: the release workflow already relies on GitHub features (GHCR with
  `GITHUB_TOKEN`, keyless signing with the GitHub OIDC token), and moving it gains nothing for this lab.
