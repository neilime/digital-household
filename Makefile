SHELL := /bin/bash
.DEFAULT_GOAL := help

HOST_UID := $(shell id -u)
HOST_GID := $(shell id -g)
TOOLING_IMAGE := digital-household-tooling:local
E2E_IMAGE := digital-household-proxmox-test:local
ISO ?= .cache/proxmox/installer.iso
ANSWER ?= .local/proxmox/answer.toml
OUTPUT ?= .local/proxmox/autoinstall.iso

.PHONY: help lint-fix ci lint setup setup-e2e test test-unit test-baseline check-ansible proxmox-download proxmox-answer-check proxmox-iso proxmox-plan proxmox-configure plan provision configure deploy verify backup
help: ## Display help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

lint: ## Execute linting
	$(call run_linter,)

lint-fix: ## Execute linting and fix
	$(call run_linter, \
		-e FIX_BIOME_FORMAT=true \
		-e FIX_BIOME_LINT=true \
		-e FIX_SPELL_CODESPELL=true \
		-e FIX_MARKDOWN=true \
		-e FIX_MARKDOWN_PRETTIER=true \
		-e FIX_YAML_PRETTIER=true \
		-e FIX_NATURAL_LANGUAGE=true \
		-e FIX_SHELL_SHFMT=true \
	)

ci: ## Execute local CI tasks
	$(MAKE) lint-fix
	$(MAKE) test
	$(MAKE) test-baseline

setup: ## Build the pinned Proxmox and Ansible tooling container
	docker build --platform=linux/amd64 --file docker/tooling/Dockerfile --target tooling \
		--build-arg UID=$(HOST_UID) --build-arg GID=$(HOST_GID) --tag "$(TOOLING_IMAGE)" .

setup-e2e: ## Build the disposable QEMU installation-test container
	docker build --platform=linux/amd64 --file docker/tooling/Dockerfile --target proxmox-test \
		--build-arg UID=$(HOST_UID) --build-arg GID=$(HOST_GID) --tag "$(E2E_IMAGE)" .

test: test-unit check-ansible ## Validate installer safety checks, native answers and Ansible syntax

test-unit: setup ## Validate installer safety checks and native answer compatibility
	$(call run_tooling,python3 -m unittest discover -s tests -p 'test_*.py' -v)

check-ansible: setup ## Validate the Proxmox playbook without connecting to a host
	$(call run_tooling,ansible-playbook -i ansible/inventory.example.yml ansible/proxmox.yml --syntax-check)

test-baseline: setup ## Apply and reapply the baseline only in a disposable container
	docker run --rm --platform=linux/amd64 --user 0:0 \
		-v "$(CURDIR):/workspace:ro" "$(TOOLING_IMAGE)" bash tests/proxmox-baseline.sh

proxmox-download: setup ## Download and verify the pinned public installation ISO
	$(call run_tooling,python3 scripts/proxmox_installer.py download --iso "$(ISO)")

proxmox-answer-check: setup ## Check the private installation answer without creating media
	$(call run_tooling,python3 scripts/proxmox_installer.py validate --answer "$(ANSWER)")

proxmox-iso: setup ## Prepare private unattended installation media; never write a device
	$(call run_tooling,python3 scripts/proxmox_installer.py prepare --answer "$(ANSWER)" --iso "$(ISO)" --output "$(OUTPUT)")

proxmox-plan proxmox-configure: setup ## Preview or apply the host baseline using explicit SSH identity and inventory
	@test -n "$(INVENTORY)" -a -f "$(SSH_KEY)" -a -f "$(KNOWN_HOSTS)" || \
		{ printf '%s\n' 'Set INVENTORY, SSH_KEY and KNOWN_HOSTS; verify the host key at the console first.' >&2; exit 2; }
	docker run --rm --platform=linux/amd64 --user "$(HOST_UID):$(HOST_GID)" \
		-v "$(CURDIR):/workspace:ro" \
		--mount "type=bind,src=$(abspath $(SSH_KEY)),dst=/run/ssh-key,readonly" \
		--mount "type=bind,src=$(abspath $(KNOWN_HOSTS)),dst=/run/known-hosts,readonly" \
		-e ANSIBLE_PRIVATE_KEY_FILE=/run/ssh-key \
		-e 'ANSIBLE_SSH_COMMON_ARGS=-o UserKnownHostsFile=/run/known-hosts' \
		"$(TOOLING_IMAGE)" ansible-playbook -i "$(INVENTORY)" ansible/proxmox.yml \
		$(if $(filter proxmox-plan,$@),--check --diff,)

plan provision configure deploy verify backup:
	@printf '%s\n' '$@ is unavailable: infrastructure implementation and deployment preflight are required.' >&2
	@exit 2

#############################
# Helpers
#############################
define run_tooling
	docker run --rm --platform=linux/amd64 --user "$(HOST_UID):$(HOST_GID)" \
		-v "$(CURDIR):/workspace" "$(TOOLING_IMAGE)" $(1)
endef

define run_linter
	@set -eu; \
	DEFAULT_WORKSPACE="$(CURDIR)"; \
	LINTER_IMAGE="digital-household-linter:latest"; \
	VOLUME="$$DEFAULT_WORKSPACE:$$DEFAULT_WORKSPACE"; \
	DEFAULT_BRANCH="$$(git -C "$$DEFAULT_WORKSPACE" rev-parse --abbrev-ref HEAD)"; \
	docker build --platform=linux/amd64 \
		--build-arg UID=$(HOST_UID) --build-arg GID=$(HOST_GID) \
		--tag "$$LINTER_IMAGE" .; \
	docker run --platform=linux/amd64 \
		-v "$$VOLUME" --rm \
		-e RUN_LOCAL=true \
		-e DEFAULT_WORKSPACE="$$DEFAULT_WORKSPACE" \
		-e DEFAULT_BRANCH="$$DEFAULT_BRANCH" \
		-e USE_FIND_ALGORITHM=false \
		-e FILTER_REGEX_INCLUDE="$(filter-out $@,$(MAKECMDGOALS))" \
		$(1) \
		"$$LINTER_IMAGE"
endef

#############################
# Positional filters for lint commands only
#############################
ifneq ($(filter lint lint-fix,$(firstword $(MAKECMDGOALS))),)
%:
	@:
endif
