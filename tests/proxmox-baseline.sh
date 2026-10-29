#!/usr/bin/env bash
set -euo pipefail

# This script is invoked only by make test-baseline inside its disposable container.
test -f /.dockerenv
test "$(id -u)" = 0
mkdir -p /run/sshd
ssh-keygen -A >/dev/null
/usr/sbin/sshd
# Seed installer-owned files and unrelated configuration to check the change boundary.
printf '%s\n' '# synthetic installer repository' >/etc/apt/sources.list.d/pve-enterprise.sources
printf '%s\n' '# synthetic installer repository' >/etc/apt/sources.list.d/ceph.sources
sha256sum /etc/apt/sources.list.d/debian.sources >/tmp/debian-sources.sha256
ansible-playbook -i localhost, tests/proxmox-baseline.yml
ansible-playbook -i localhost, tests/proxmox-baseline.yml --check >/tmp/baseline-recheck.txt
grep -Eq 'changed=0 .*failed=0' /tmp/baseline-recheck.txt
sshd -T >/tmp/effective-sshd.txt
grep -Fx 'passwordauthentication no' /tmp/effective-sshd.txt
grep -Fx 'kbdinteractiveauthentication no' /tmp/effective-sshd.txt
grep -Fx 'permitrootlogin without-password' /tmp/effective-sshd.txt
grep -Fx 'allowagentforwarding no' /tmp/effective-sshd.txt
grep -Fx 'Components: pve-no-subscription' /etc/apt/sources.list.d/digital-household-proxmox.sources
test ! -e /etc/apt/sources.list.d/pve-enterprise.sources
test ! -e /etc/apt/sources.list.d/ceph.sources
sha256sum --check /tmp/debian-sources.sha256
ansible-playbook -i localhost, tests/proxmox-baseline.yml -e proxmox_repository_channel=enterprise
grep -Fx 'Components: pve-enterprise' /etc/apt/sources.list.d/digital-household-proxmox.sources
grep -Fx 'URIs: https://enterprise.proxmox.com/debian/pve' /etc/apt/sources.list.d/digital-household-proxmox.sources
printf '%s\n' 'Baseline applies, preserves key-only SSH, and is idempotent.'
