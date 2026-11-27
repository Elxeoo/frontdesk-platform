# ADR-0008: Kyverno blocks new pods when it cannot decide

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

Kyverno runs as an admission webhook. It checks image signatures (`require-signed-images`) and, in the
`frontdesk` namespace, the pod baseline (`pod-baseline`). When Kyverno is down, or when GHCR or Sigstore
cannot be reached during signature verification, the API server has to choose between admitting the pod
anyway (`Ignore`) and rejecting it (`Fail`). Neither policy sets `failurePolicy`, so the default applies;
`kubectl get validatingwebhookconfigurations` shows `Fail` for both webhooks.

## Decision

Keep `Fail`. With `Ignore`, an outage would switch the checks off silently: any image, unsigned ones
included, would start, and nothing would report it. With `Fail`, an outage stops new pods but never
admits a pod that the policies would reject. We expect GHCR and Sigstore outages to be rare and short,
and pods that are already running are not affected.

## Consequences

- While Kyverno is unavailable, pods that these policies match cannot be created: no deployments, and a
  pod that is deleted or evicted is not replaced until Kyverno is back. The same applies to images from
  `ghcr.io/elxeoo` while GHCR or Sigstore is unreachable.
- Kyverno restarts and upgrades open a short window without new pods. On AKS, more admission controller
  replicas will shorten it.
- The policy files rely on the default, so a later Kyverno release that changed it would change this
  behavior. Next step: set `failurePolicy: Fail` explicitly in both policies.
