#!/usr/bin/env bash
set -euo pipefail

# Run only in the disposable QEMU test container.
test -f /etc/digital-household-disposable-test
test -r /dev/kvm && test -w /dev/kvm
cd /var/tmp/proxmox-e2e
mkdir -p "$REPORTS_DIR"
pytest tests/proxmox/test_installation.py --junitxml="$REPORTS_DIR/proxmox.xml" \
	--tb=short -o junit_logging=no
