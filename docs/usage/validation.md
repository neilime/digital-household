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
The job requires `/dev/kvm`, Docker and disk-backed checkout storage.

The job builds the checksum-verified Proxmox ISO using the existing tooling and
synthetic answer fixture. Each run generates a temporary SSH key and password
hash. The adjacent GitHub Script module stages an explicit source allowlist and
runs the `proxmox-test` stage of the [tooling Dockerfile](../../docker/tooling/Dockerfile).
Ignored private inventory and the host checkout are excluded from the container.

The container runs as the runner's UID/GID, with access to `/dev/kvm` and the
private fixture directory only. It has no Docker socket, host networking,
published ports or privileged mode. The test's SSH forwarding binds to loopback
inside the container. Initial host-key trust is restricted to that owned endpoint;
later connections enforce the recorded key. QEMU runs on the runner's kernel;
there is no intermediate Lima VM.

[The installation tests](../../tests/proxmox/test_installation.py) use KVM, UEFI,
two vCPUs, 4 GiB RAM and a new 32 GiB sparse raw disk. The disk and installation
inputs live on the runner's checkout filesystem, mounted at `/var/tmp/proxmox-e2e`.
The tests reject RAM-backed storage and fail if KVM is unavailable. Direct I/O
bypasses the file cache while honoring guest flush requests. No host block device
is attached to QEMU.

The installer has a 15-minute deadline within a 40-minute test step. Five-minute
samples record VM state, disk writes and free space for timeout diagnosis.

The tests verify:

- Unattended installation powers off and the installed disk boots without the ISO.
- Proxmox kernel, UEFI boot, disk storage, management services and web UI work.
- The disk serial, static management bridge, route and hostname match the answer; DNS lookup works.
- The actual deployment playbook passes its target checks and applies the baseline.
- Reapplication and check mode report no changes; Debian package sources are preserved.
- Package indices refresh successfully and key-only SSH persists after reboot.

[The container entrypoint](../../tests/proxmox/run.sh) writes native pytest JUnit
into `reports/proxmox.xml` under the private fixture directory. Pinned Hoverkraft
reporting actions publish summaries, annotations and a distinct installation PR
comment. Fork and Dependabot PRs skip comments. Completed JUnit is uploaded even
when tests or reporting fail, with seven-day retention. An installer timeout also
produces a synthetic console image, uploaded separately for one day. Uploads
select these exact files; raw VM logs, disks, keys and prepared media stay private.

The fixture stops its QEMU child after success or failure. An `always()` workflow
step removes the invocation's container, including any remaining processes,
before deleting its private inputs and disk. Cleanup failures fail the job.
Forced runner termination is bounded by hosted-runner disposal.

These checks qualify the virtual installation path. Physical disk/NIC compatibility,
target-console approval, Home Assistant boot, radio devices and recovery remain
separate acceptance tasks. Never boot the synthetic media on physical hardware.

`make plan`, `provision`, `configure`, `deploy`, `verify` and `backup` fail with an
explicit message until their implementations are delivered. These commands never
report success for an absent infrastructure stack.
