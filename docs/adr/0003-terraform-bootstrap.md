# ADR-0003: Terraform bootstrap for state, budget and pipeline identity

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

Terraform keeps its state in a file. The pipeline that will run Terraform needs that file in shared storage, an
identity to sign in with, and a budget alert in place before anything costly exists. All three have to exist
before the pipeline's first run, so the pipeline cannot create them. The storage for the state is itself an Azure
resource, so it cannot hold its own state while it is being created.

## Decision

A separate Terraform root, `infra/terraform/bootstrap`, creates these resources and is applied by hand:

- A resource group, storage account and `tfstate` container in Austria East. Shared key access is disabled, so
  access goes through Entra ID only. Blob versioning and 7-day soft delete protect the state file, and
  `prevent_destroy` guards the account.
- A monthly budget of 25 USD at subscription scope, with email alerts at 50, 80 and 100 percent of actual cost
  and 100 percent of forecasted cost. Subscription scope also covers the resource group AKS creates for its nodes.
- A user-assigned managed identity for the pipeline: Contributor and Role Based Access Control Administrator on
  `rg-frontdesk-dev`, Storage Blob Data Contributor on the state container.

The first apply wrote its state locally, because the storage did not exist yet. After that apply the state was
moved into the container with `terraform init -migrate-state`, and the local copy was deleted. The bootstrap
state now lives in the container it created.

## Consequences

**Positive**

- No secret exists for state access or for the pipeline identity.
- State has locking (blob lease), version history and soft delete.
- The resources the pipeline depends on are in code and can be recreated from it.

**Negative**

- Bootstrap changes are applied from a workstation, not by the pipeline, so they skip the pipeline's plan and
  approval steps.
- The operator's data role is granted to whoever runs the apply; another operator would replace it.
- The state account uses LRS: one copy set in one region.

## Alternatives considered

- **Create the storage by hand in the portal.** Rejected: it would not be in code and could drift unnoticed.
- **Keep the state local.** Rejected: no shared access for the pipeline, no locking, and a lost laptop loses it.
- **HCP Terraform for state.** Rejected: one more account and vendor for a single-operator lab.
