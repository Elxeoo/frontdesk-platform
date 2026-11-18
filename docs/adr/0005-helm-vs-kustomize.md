# ADR-0005: Kustomize for our manifests, Helm for third-party software

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

The cluster runs two kinds of software. Our own application (api, web, night-audit, the database Cluster
and the migration Job) is about ten manifests that we write, and they differ between environments in only
a few fields: today the replica count and the image digest. Argo CD and the CloudNativePG operator are
written by their projects and published as Helm charts; the Argo CD chart alone has about 5,000 lines of
default values.

Argo CD deploys both from Git, so the question is how each is described in the repository.

## Decision

- **Our manifests use Kustomize.** `deploy/base` holds plain YAML, and each environment has an overlay with
  only its differences (`deploy/overlays/local` sets one api replica and pins images by digest). There is no
  template language to learn or debug, and `kubectl kustomize` shows exactly what Argo CD will apply.
- **Third-party software uses the projects' Helm charts.** Each chart is an Argo CD Application with a
  pinned chart version (`platform/argocd/apps/argocd.yaml`, `platform/argocd/apps/cnpg.yaml`). Only the
  values we change live in the repository (`platform/argocd/values.yaml`); everything else keeps the chart
  defaults.

## Rollback

Helm keeps a numbered revision for every install and upgrade, and `helm rollback` re-applies an earlier
revision directly to the cluster. In this setup that is not a rollback:

- Argo CD renders the charts itself and applies the result; it never runs `helm upgrade`. The Helm release
  records from the first manual install no longer change, so `helm list` and `helm history` are stale.
- `helm rollback` changes the cluster but not Git, so selfHeal reverts it.
- Argo CD's own History and Rollback is refused while automated sync is on.

A change is rolled back by reverting its commit in Git (`git revert`, then a pull request). Argo CD applies
the previous state like any other change, and the rollback is reviewed and recorded.

## Consequences

**Positive**

- Our manifests stay plain YAML that anyone who knows Kubernetes can read.
- Upgrading Argo CD or the operator is a one-line change to a chart version, reviewed in a pull request.
- A rollback goes through Git and leaves the same trail as any other change.

**Negative**

- Two tools to know, and debugging a chart means reading templates written by someone else.
- Chart versions are pinned in two places, the Applications and the `Makefile` bootstrap, and must change
  together.
- The stale Helm release records can mislead someone who runs `helm list`.

## Alternatives considered

- **Our own Helm chart.** Rejected: templating ten manifests with two differences adds a language and its
  errors for no gain.
- **Render third-party charts once and commit the YAML.** Rejected: an upgrade would mean regenerating and
  reviewing thousands of lines instead of changing one version number.
