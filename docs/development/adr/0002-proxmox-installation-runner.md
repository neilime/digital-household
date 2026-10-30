# ADR 0002: Direct QEMU for Proxmox installation tests

Date: 2026-10-30

Status: Accepted. Hosted qualification is required before merging the implementation.

## Context

The installation scenario must boot the actual unattended ISO, then test the
installed host and its Ansible baseline. Running it inside a Lima guest adds
another virtualization layer on GitHub-hosted runners.

On 2026-10-29, the complete Lima/QEMU scenario passed locally in 6m19s, while
[the hosted run](https://github.com/neilime/digital-household/actions/runs/40955800259)
at `5662cc8e697a5007261b2a9c141b559714c99244` timed out after 30 minutes at
69.9% package extraction. Disk writes continued and guest storage remained
available. This evidence establishes a hosted performance problem, without
identifying its precise cause.

## Decision

Run the installer directly in QEMU on GitHub-hosted runners, inside a disposable
Docker container with KVM access. The owner selected this approach on 2026-10-30
instead of requiring a dedicated KVM runner. Keep shared VM actions for other
Linux guest scenarios and reuse Hoverkraft's report parser and PR comment action.

## Consequences

The container provides a reproducible test environment without another VM layer.
It receives synthetic inputs, a new disk file and `/dev/kvm`; installation never
targets a physical disk. The consumer owns this scenario's QEMU lifecycle and
container cleanup. Hosted runners must expose KVM and provide enough disk space.

A successful hosted run remains necessary to qualify this implementation.
Physical installation, nested HAOS boot and recovery require separate validation.
