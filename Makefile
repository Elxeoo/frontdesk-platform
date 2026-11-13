CLUSTER_CONFIG := infra/k3d/cluster.yaml
OVERLAY := deploy/overlays/local
CNPG_CHART_VERSION := 0.29.1

.PHONY: up down test lint

up:
	k3d cluster create --config $(CLUSTER_CONFIG)
	helm repo add cnpg https://cloudnative-pg.github.io/charts --force-update
	helm upgrade --install cnpg cnpg/cloudnative-pg --version $(CNPG_CHART_VERSION) --namespace cnpg-system --create-namespace --wait
	kubectl apply -k $(OVERLAY)

down:
	k3d cluster delete frontdesk

test:
	cd app && .venv/bin/pytest

lint:
	cd app && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	kubectl kustomize $(OVERLAY) > /dev/null
