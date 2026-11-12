CLUSTER_CONFIG := infra/k3d/cluster.yaml
OVERLAY := deploy/overlays/local

.PHONY: up down test lint

up:
	k3d cluster create --config $(CLUSTER_CONFIG)
	kubectl apply -k $(OVERLAY)

down:
	k3d cluster delete frontdesk

test:
	cd app && .venv/bin/pytest

lint:
	cd app && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	kubectl kustomize $(OVERLAY) > /dev/null
