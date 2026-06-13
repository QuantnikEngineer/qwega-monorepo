SHELL := /bin/bash

# Required for any remote target. Override on the command line:
#   make deploy HOST=ec2-1-2-3-4.compute.amazonaws.com
HOST       ?=
SSH_USER   ?= ec2-user
REMOTE_DIR ?= /opt/quantnik

SSH := ssh $(SSH_USER)@$(HOST)

# On Apple Silicon you need linux/amd64 for an Intel EC2. Drop or change for Graviton.
PLATFORM ?= linux/amd64

.PHONY: help build sync deploy restart stop logs ps ssh check-host

help:
	@echo "Usage: make <target> HOST=<your-host> [SSH_USER=ec2-user] [REMOTE_DIR=/opt/quantnik]"
	@echo
	@echo "Targets:"
	@echo "  build    Sanity-build the docker image locally ($(PLATFORM))"
	@echo "  sync     Rsync source to the remote (excludes node_modules, dist, data, .env, .git)"
	@echo "  deploy   sync + remote 'docker compose up -d --build' + ps"
	@echo "  restart  docker compose restart on the remote"
	@echo "  stop     docker compose down on the remote"
	@echo "  logs     Tail the remote container logs"
	@echo "  ps       Show remote container status"
	@echo "  ssh      Open an interactive shell on the remote"

check-host:
	@if [ -z "$(HOST)" ]; then \
	  echo "HOST is required. Example: make deploy HOST=ec2-1-2-3-4.compute.amazonaws.com"; \
	  exit 1; \
	fi

build:
	docker build --platform $(PLATFORM) -t quantnik:latest .

sync: check-host
	rsync -avz --delete \
	  --exclude node_modules \
	  --exclude dist \
	  --exclude data \
	  --exclude .env \
	  --exclude .git \
	  --exclude .vite \
	  ./ $(SSH_USER)@$(HOST):$(REMOTE_DIR)/

deploy: sync
	$(SSH) "cd $(REMOTE_DIR) && docker compose up -d --build"
	$(SSH) "cd $(REMOTE_DIR) && docker compose ps"

restart: check-host
	$(SSH) "cd $(REMOTE_DIR) && docker compose restart"

stop: check-host
	$(SSH) "cd $(REMOTE_DIR) && docker compose down"

logs: check-host
	$(SSH) "cd $(REMOTE_DIR) && docker compose logs -f --tail=200 quantnik"

ps: check-host
	$(SSH) "cd $(REMOTE_DIR) && docker compose ps"

ssh: check-host
	$(SSH)
