# Validate the repository

Static validation requires Docker and GNU Make. `make lint` runs the same pinned
Hoverkraft linter used in CI, including YAML, workflow, IaC and secret checks.

`make test` builds the pinned tooling image, tests installer input validation,
checksum failures and preservation of existing/private files, and checks the
Ansible playbook syntax. Native answer validation runs against the actual
Proxmox assistant. `make test-baseline` applies the role as root inside a fresh
Debian container, checks effective SSH configuration, preserves Debian APT
sources, verifies both Proxmox channels and checks an unchanged preview.
These host-changing tests must never run directly on the workstation.

The bootstrap CI job runs the installer unit tests and the same container
assertions through the shared Ansible test action. Its native JUnit reports are
separate from the installation end-to-end results below.

The installation end-to-end test runs on GitHub-hosted Linux runners through
[the shared CI job](../../.github/workflows/shared-ci.yml). Pull requests and
main pushes run it automatically; the main workflow also supports manual runs.
The job requires KVM, Docker for ISO preparation and sufficient disk-backed storage.

The job builds the checksum-verified Proxmox ISO with synthetic installation
settings, a temporary SSH key and password hash. The adjacent GitHub Script module
prepares only these inputs and a JSON VM configuration.

The shared `vm/create` action boots QEMU directly on the runner with UEFI, two
vCPUs, 4 GiB RAM and a private 32 GiB raw disk. Its QEMU backend waits for installer
power-off, boots the disk without the ISO and waits for SSH. Installer shutdown
and SSH readiness use the 20-minute startup deadline; preparation and subprocesses
have their own limits. No host block device is attached.

The shared `ansible/test-molecule` action runs [the Molecule scenario](../../tests/proxmox/molecule/installation/molecule.yml)
with a 20-minute budget. It installs pinned test tools and publishes their reports.
This repository's inventory connects to the disposable VM through the creation
step's SSH outputs. Its scenario defines the sequence: apply the real baseline, verify it, check
idempotence, reboot and repeat verification and idempotence. The scenario also
exercises check mode. The shared `vm/test` action then runs
[the Goss suite](../../tests/proxmox/goss.yaml) using variables derived from the
synthetic installer answer. Tool installation, SSH handling and report collection
belong to the shared actions. The Molecule action itself requires no VM and imposes
no reboot policy; this installation test explicitly needs both.

The tests verify:

- Unattended installation powers off and the installed disk boots without the ISO.
- Proxmox kernel, UEFI boot, disk storage, management services and web UI work.
- The disk serial, static management bridge, route and hostname match the answer; DNS lookup works.
- The actual deployment playbook passes its target checks and applies the baseline.
- Reapplication reports no changes, check mode completes and Debian package sources are preserved.
- Package indices refresh successfully and key-only SSH persists after reboot.

The shared actions publish native Ansible and Goss JUnit, summaries, annotations
and stable PR comments. Molecule also publishes the scenario status, including
idempotence and timeout failures. Completed reports are uploaded after failures.
Fork and Dependabot runs skip comments. Reports have seven-day retention;
runtime directories, logs, keys and prepared media remain private.

An `always()` step calls `vm/destroy`, which verifies process ownership and
termination before deleting the private disk and keys. A final consumer step
removes its synthetic installation inputs. Cleanup failures fail the job;
forced runner termination is bounded by hosted-runner disposal.

These checks qualify the virtual installation path. Physical disk/NIC compatibility,
target-console approval, Home Assistant boot, radio devices and recovery remain
separate acceptance tasks. Never boot the synthetic media on physical hardware.

`make plan`, `provision`, `configure`, `deploy`, `verify` and `backup` fail with an
explicit message until their implementations are delivered. These commands never
report success for an absent infrastructure stack.
