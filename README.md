# FrontDesk Platform

A hotel front-desk application running on a platform I am building myself: signed container images,
policy-as-code, GitOps delivery, SLO-based canary releases, and Azure infrastructure provisioned with
Terraform and Azure Pipelines.

> **Status:** work in progress. This README describes the target; a part is marked as done only after
> it has been built and tested.

## Why this project

Before moving into cloud and DevOps, I worked at a hotel front desk. At the desk, two things matter most:
the system has to be up while a guest is standing in front of you, and a bad change must never lose a
reservation.

This project turns that experience into a platform question: how do you ship changes to a front-desk
application often, without putting check-in at risk?

## What it will do (planned)

| Area | Plan |
| --- | --- |
| Application | Reception screen, reservation API, nightly audit job, PostgreSQL |
| Containers | Small, non-root images; scanned for known vulnerabilities and signed |
| Policy | The cluster admits only signed images that follow the rules |
| Delivery | GitOps: the cluster follows what is in Git; new versions roll out as a canary and are promoted or rolled back based on SLO metrics |
| Observability | Metrics, dashboards and alerts to Telegram |
| Infrastructure | A local cluster first, then Azure Kubernetes Service, provisioned with Terraform and Azure Pipelines |

## Repository layout (planned)

| Path | Contents |
| --- | --- |
| `app/` | API, nightly audit job, database migrations, application tests |
| `web/` | Reception screen |
| `deploy/` | Kubernetes manifests for the application |
| `platform/` | Cluster components: GitOps, policy, monitoring |
| `infra/` | Local k3d cluster config; Terraform for Azure |
| `.github/` | CI workflows |
| `scripts/` | Smoke tests and helper scripts |
| `docs/` | Contracts, architecture diagrams, decision records (ADRs) |

## Local development

Requires Docker, k3d, kubectl and Helm. `make test` and `make lint` use the virtual environment in `app/.venv` (setup in [app/README.md](app/README.md)).

| Command | What it does |
| --- | --- |
| `make up` | Creates the local k3d cluster, installs the CloudNativePG operator with Helm and applies `deploy/overlays/local` |
| `make down` | Deletes the local cluster |
| `make test` | Runs the application tests; database tests are skipped unless `TEST_DATABASE_URL` is set |
| `make lint` | Checks the code with ruff and renders the Kubernetes manifests |

## Conventions

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`type(scope): summary`), so the type of each change shows which part of the version number it bumps.

## Known limitations

- **No SBOM attestation.** Images are scanned and signed, but no software bill of materials is generated or attached to them. Cut to fit the project timeline. Next step: generate a CycloneDX SBOM with Trivy in `release.yml` and attach it to the image digest with `cosign attest`.

## License

MIT. See [LICENSE](LICENSE).
