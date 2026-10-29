#!/usr/bin/env bash
set -euo pipefail

# Never run this scenario directly on a developer workstation.
test -f /etc/digital-household-disposable-test
test -r /dev/kvm && test -w /dev/kvm
cd /var/tmp/proxmox-e2e
python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r docker/tooling/requirements.txt -r tests/proxmox/requirements.txt
export PATH="$PWD/.venv/bin:$PATH"
export ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg"
pytest tests/proxmox/test_installation.py --junitxml="$REPORTS_DIR/proxmox.xml" \
	--tb=short -o junit_logging=no
