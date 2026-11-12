# Tool versions

Versions used to build and run this project. Updated when a tool is upgraded.

| Tool | Version | Recorded | Note |
| --- | --- | --- | --- |
| Kubernetes (k3s) | v1.37.2+k3s1 | 2026-11-12 | Local cluster image, pinned in `infra/k3d/cluster.yaml`; AKS GA since Oct 2026 |
| kubectl | v1.37.2 | 2026-11-12 | Within ±1 minor of the cluster |
| Kustomize | v5.8.1 | 2026-11-12 | Built into kubectl |
| k3d | v5.9.0 | 2026-11-12 | |
| Docker Engine | 29.1.3 | 2026-11-03 | Inside WSL |
| Helm | 3.22.0 | 2026-11-03 | |
| Terraform | 1.17.1 | 2026-11-04 | |
| gh | 2.103.3 | 2026-11-04 | |
| Trivy | 0.76.1 | 2026-11-04 | |
| k9s | 0.51.0 | 2026-11-04 | |
| kubelogin | 0.2.22 | 2026-11-04 | |
| TFLint | 0.65.0 | 2026-11-04 | |
| k6 | 2.3.0 | 2026-11-04 | |
| kubectl-cnpg | 1.30.1 | 2026-11-04 | |
| kubectl-argo-rollouts | 1.10.1 | 2026-11-04 | |
| cosign | 3.1.4 | 2026-11-11 | |
