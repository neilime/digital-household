# Infrastructure boundaries

Repository: `neilime/digital-household`. Scope: Proxmox, Home Assistant, personal services and family integrations.

This repository owns one independent trust domain. Future OpenTofu state must use
its own backend object namespace, access identity and encryption configuration.
No backend or deployment credential is configured during bootstrap. Local state,
plans, private variables, keys and private inventory are ignored by Git. Review
ignore rules before adding new state formats; an ignore rule is not secret scanning.

Human credentials and recovery keys stay in Bitwarden with identities dedicated
to this domain. Public defaults and synthetic CI fixtures may be committed.
Operational data, raw backups and authenticated test artifacts must remain outside
this public repository. PR CI uses no account credentials.

The `production` environment is reserved for reviewed deployments from protected
branches, with an explicit reviewer gate. No workflow currently deploys or spends
money. Main-branch rules require a pull-request review. Review each CI job's result
before merging.
A PR author cannot approve their own PR; another eligible reviewer is required.

Dependencies are pinned to immutable Action commits, Docker digests and tooling
versions. See [update ownership](../../CONTRIBUTING.md#repository-automation).
Workflows compose shared Ansible validation and report publication, and own cleanup
conditions. Linux guest scenarios use the shared VM lifecycle actions at one
revision. The Proxmox installation scenario runs QEMU in a disposable container
with KVM access; see [ADR 0002](adr/0002-proxmox-installation-runner.md). Review
shared CI updates with the affected scenarios before merging.

The bootstrap targets compatible hosts without depending on a manufacturer or
machine model. Disk and NIC identity, network settings and hostname belong in
each host's private answer and inventory. The
[supported host profile](../usage/proxmox-bootstrap.md#supported-host-profile)
defines the current architecture, storage and networking requirements.

The native Proxmox installer owns the initial disk layout and host networking.
The repository wrapper verifies the source image and enforces the private-answer
and exact-target policy before invoking that installer. Ansible owns the ongoing
host baseline; it requires a known SSH host key and verifies the target before
changes. The current baseline manages APT sources and SSH configuration only.
Private answers, prepared media and inventory stay in ignored `.local/` paths.

OpenTofu will own HAOS VM resources. No VM state backend, HAOS deployment or
backup implementation is present yet. See the [bootstrap guide](../usage/proxmox-bootstrap.md)
and [validation scope](../usage/validation.md) for operational boundaries.
