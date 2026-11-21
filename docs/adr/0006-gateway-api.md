# ADR-0006: Gateway API with Traefik instead of Ingress

- **Status:** Accepted
- **Date:** 2026-11-21

## Context

The web screen and the api need one entry point from outside the cluster, routed by host name and path.
Kubernetes offers two APIs for this. Ingress is frozen: it stays in Kubernetes but gets no new features.
Gateway API is its successor and is where the Kubernetes project points new work.

The most widely used Ingress controller, ingress-nginx, was retired in March 2026. It no longer gets
releases, bug fixes or security fixes. The entry point is the only part of the cluster that faces the
outside, so it has to run software that still receives security fixes.

## Decision

- **Routing uses Gateway API.** `deploy/base/httproute.yaml` sends `frontdesk.localhost/api` to the api
  Service and everything else to web. It uses only standard Gateway API fields, so it does not change if
  the implementation does.
- **Traefik implements it.** The Traefik chart 42.4.1 (Traefik v3.7.19) is its own Argo CD Application
  (`platform/argocd/apps/traefik.yaml`) and creates the GatewayClass and the Gateway `traefik-gateway`.
  The Traefik bundled with k3s is disabled, so the version comes from Git, as it will on AKS.
- **The Gateway API CRDs are a separate Application** (`platform/argocd/apps/gateway-api.yaml`), pinned to
  v1.6.3, the version Traefik v3.7 documents support for.

## Consequences

- Ingress is built into Kubernetes; Gateway API is not. Its CRDs are one more Application to maintain, and
  prune stays off for them, because deleting a CRD deletes every resource of that kind.
- The CRD version follows Traefik, not the newest Gateway API release (v1.7.0 at the time of writing).
- On an empty cluster the CRDs can arrive after Traefik and the frontdesk app, so both retry their first
  sync (5 attempts, backing off from 10 s up to 3 min).
- The listener accepts routes from every namespace (`from: All`). With one application namespace this is
  enough; a namespace selector is the next step if the cluster is shared.
- nginx in the web image still forwards `/api/` to the api. Through the Gateway that path is unused; it
  remains for `compose.yaml`, where web is the only published port.

## Sources

- Ingress NGINX retirement: https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/
- Steering Committee statement: https://kubernetes.io/blog/2026/01/29/ingress-nginx-statement/
- Ingress API is frozen: https://kubernetes.io/docs/concepts/services-networking/ingress/
- Traefik Gateway API support: https://doc.traefik.io/traefik/reference/install-configuration/providers/kubernetes/kubernetes-gateway/
