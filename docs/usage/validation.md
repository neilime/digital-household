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

VM validation runs on GitHub-hosted Linux runners through
[the shared CI job](../../.github/workflows/shared-ci.yml). Pull requests and
main pushes run it automatically; the main workflow also supports manual runs.
The job composes the pinned `vm/create`, `vm/test` and `vm/destroy` actions,
using [our assertions](../../tests/e2e.sh). Keep all three actions on the same
immutable revision. The creation action installs Lima and QEMU on the runner.
This job uses the supported `ubuntu-24.04` runner because `ci-github-iac` 0.2.0
stores Lima runtimes under `/tmp`. The larger nested workload requires disk-backed
host storage; Ubuntu 26.04 defaults `/tmp` to RAM-backed storage. Moving this job
to that runner requires a shared-action release with a disk-backed runtime path.
The outer guest still uses the pinned Ubuntu 26.04 image.

`vm/test` parses results, renders summaries and annotations, updates a PR comment
and uploads completed reports. Its stable `report-name` keeps comments distinct;
fork and Dependabot PRs skip comments. The parser manages its own dependencies.
The workflow grants `pull-requests: write`
and schedules destruction with `always()`, including after reporting failure.
Use `command` instead of `test-script` for inline guest commands. Optional
`coverage: codecov` requires explicit report selection and `id-token: write`.

The installation scenario builds the real, checksum-verified Proxmox ISO using
the existing tooling and synthetic answer fixture. Each run generates a temporary
SSH key and password hash. Only explicitly selected source files and these test
inputs are copied into the isolated Ubuntu guest; ignored private inventory is
excluded. The host checkout is not mounted in that guest.
Large test inputs and the nested disk use `/var/tmp` on the guest's disk-backed
filesystem. Ubuntu's RAM-backed `/tmp` is reserved for small temporary reports;
the test rejects a RAM-backed working directory before starting installation.

[The Lima configuration](../../tests/lima.yml) reserves four vCPUs, 6 GiB of RAM
and a 30 GiB sparse disk. It exposes the host CPU's virtualization extensions.
Inside that VM, [the installation tests](../../tests/proxmox/test_installation.py)
use QEMU with KVM, UEFI, two vCPUs, 4 GiB RAM and a new 32 GiB sparse raw disk.
Raw storage avoids a second copy-on-write layer; `cache=none` bypasses the outer
guest's file cache while honoring guest flush requests. The test fails if nested
KVM is unavailable; software emulation is not used.
The installer has a 30-minute deadline within a 45-minute test allowance.
Five-minute samples record VM state and disk writes, helping distinguish slow
package extraction on hosted runners from a stalled installation.
The inner VM's SSH port binds only to loopback in the outer guest. Initial host-key
trust is restricted to that owned endpoint; later connections enforce the recorded key.

The tests verify:

- Unattended installation powers off and the installed disk boots without the ISO.
- Proxmox kernel, UEFI boot, disk storage, management services and web UI work.
- The disk serial, static management bridge, route, DNS and hostname match the answer.
- The actual deployment playbook passes its target checks and applies the baseline.
- Reapplication and check mode report no changes; Debian package sources are preserved.
- Package indices refresh successfully and key-only SSH persists after reboot.

Pytest writes native JUnit to `REPORTS_DIR`; `vm/test` collects and publishes it,
including failures. The fixture stops its QEMU child even if installation or an
assertion fails. The workflow always destroys the outer VM and removes the private
answer, key and prepared ISO from the runner. Installer timeouts include VM state
and available disk space in JUnit, plus a separate console image retained for one
day. This console belongs only to the synthetic installation. Raw VM logs, disks,
keys and prepared media are not uploaded. Forced runner termination is bounded
by hosted-runner disposal.

These checks qualify the virtual installation path. Physical disk/NIC compatibility,
target-console approval, Home Assistant boot, radio devices and recovery remain
separate acceptance tasks. Never boot the synthetic media on physical hardware.

Each invocation uses its own short private Lima runtime under `/tmp`, removed
with its keys after verified teardown. Each test keeps its own sanitized report.
CI uses the report path returned by the action from runner temp.
To collect reports from test tools, set `report-file` patterns on the test action and write
those files into the supplied guest `REPORTS_DIR`. The parser consumes the
`report-files` output when present, otherwise the command-status `report`.
Collected report contents must be suitable for these public workflows.
For input options and cleanup recovery, see the generated action documentation:
[create](https://github.com/hoverkraft-tech/ci-github-iac/blob/0.2.0/actions/vm/create/README.md),
[test](https://github.com/hoverkraft-tech/ci-github-iac/blob/0.2.0/actions/vm/test/README.md) and
[destroy](https://github.com/hoverkraft-tech/ci-github-iac/blob/0.2.0/actions/vm/destroy/README.md).

`make plan`, `provision`, `configure`, `deploy`, `verify` and `backup` fail with an
explicit message until their implementations are delivered. These commands never
report success for an absent infrastructure stack.
