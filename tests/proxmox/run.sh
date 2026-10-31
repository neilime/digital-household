#!/usr/bin/env bash
set -euo pipefail

# The workflow supplies only the disposable VM's private SSH configuration.
: "${VM_SSH_CONFIG:?}" "${VM_DIRECTORY:?}" "${E2E_DIRECTORY:?}" "${REPORTS_DIR:?}"
venv=$(mktemp -d)
trap 'rm -rf "$venv"' EXIT
python3 -m venv "$venv"
"$venv/bin/pip" install --quiet -r docker/tooling/requirements.txt -r tests/proxmox/requirements.txt
export PATH="$venv/bin:$PATH"
export ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg"
export ANSIBLE_HOME="$venv/ansible"
pytest tests/proxmox/test_installation.py --junitxml="$REPORTS_DIR/proxmox.xml" \
	--tb=short -o junit_logging=no
