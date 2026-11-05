# ADR-0001: Repository location and layout

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

One maintainer builds and runs every layer of this project: the application (API, nightly audit job, reception
screen), its container images, the Kubernetes manifests, the cluster platform components and the Azure
infrastructure.

The workstation runs Windows. The toolchain does not: Docker, k3d, kubectl, Helm, Terraform and the shell scripts
all target Linux first, the containers are Linux, and the CI runners and pipeline agents are Linux.

Many changes cut across layers. A new endpoint, for example, can touch the application code, a probe or setting in
the manifests and a step in CI at the same time.

## Decision

1. The repository lives on the WSL 2 Linux filesystem (`~/projects/frontdesk-platform`), not on the Windows drive.
   All work, including Git operations, happens from the Linux side.
2. Everything lives in a single repository with one top-level directory per concern: `app/`, `web/`, `deploy/`,
   `platform/`, `infra/`, `.github/`, `scripts/` and `docs/`.
3. Text files use LF line endings, enforced by `.gitattributes`.

## Consequences

**Positive**

- The local environment matches the containers and CI: same shell, LF line endings, executable file modes and
  case-sensitive paths. Problems show up on the workstation instead of in the pipeline.
- The native Linux filesystem is fast. A repository under `/mnt/c` is slow to access from WSL and does not keep
  Linux file permissions reliably.
- A change that spans layers is one pull request, reviewed and tested as a whole, with one history to read.
- One ruleset and one set of required checks protect everything. Argo CD can track `deploy/` and `platform/` in the
  same repository that produces the images.

**Negative**

- Working on Windows requires WSL 2 (or a dev container); native Windows tooling is not supported.
- CI must not run every job on every change as the repository grows. Workflow-level path filters cannot be used for
  required checks, because a skipped required check stays pending and blocks merging. Selective runs have to be
  decided inside a workflow that always runs.
- Automated commits to `deploy/` (image digest updates) must not trigger new image builds, or CI loops on itself.
- Write access is repository-wide. With more contributors, `CODEOWNERS` or a separate repository would be needed to
  restrict who can change `infra/` or `deploy/`.

## Alternatives considered

- **Repository on the Windows drive with Windows tooling.** Rejected: the tools, containers and CI are Linux, so line
  endings, file modes and scripts would behave differently locally than in CI.
- **One repository per concern (application, deployment configuration, infrastructure).** Common in larger
  organizations, often with a separate GitOps configuration repository. It gives isolation and per-repository access
  control, but for a single maintainer it multiplies pull requests and adds coordination between repositories. To be
  revisited if the team grows or the deployment configuration needs separate access control.
