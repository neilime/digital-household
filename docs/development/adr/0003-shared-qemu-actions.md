# ADR 0003: Shared direct-QEMU actions

Date: 2026-10-31

Status: Proposed; merge requires a reviewed shared-action release.

## Context

[ADR 0002](0002-proxmox-installation-runner.md) chose direct QEMU after the nested
Lima scenario timed out on hosted runners. The direct implementation passed
[hosted CI](https://github.com/neilime/digital-household/actions/runs/40979527334),
but left reusable VM lifecycle and report publication in the consumer.

## Decision

Keep direct QEMU and move its lifecycle into `ci-github-iac`'s existing create,
test and destroy actions. The consumer prepares synthetic installation inputs,
selects explicit VM resources and retains Proxmox assertions. The native
`ansible/test-molecule` scenario owns inventory, deployment, idempotence, check
mode and reboot, connecting through the creation action's private SSH outputs.
`vm/test` executes the Goss platform assertions in the guest. These test actions
own tool installation, report collection, parsing, comments and artifacts.

## Consequences

This supersedes the consumer-owned Docker/QEMU lifecycle in ADR 0002. ISO tooling
still runs in its pinned container. `vm/create` installs QEMU, and the Ansible
actions install isolated test runtimes. Changes require a shared release; all
five infrastructure actions must use the same immutable pin.
Real hardware and Home Assistant qualification remain separate acceptance tasks.

## Qualification evidence

On 2026-11-04, [shared CI](https://github.com/hoverkraft-tech/ci-github-iac/actions/runs/41841444203)
passed all 24 jobs at `6bd5dbe6bde57182c5f2109dda4968160be9ed31`.
[Consumer CI](https://github.com/neilime/digital-household/actions/runs/41841668084)
passed all six jobs at `1eb1c88691135a36e30e7c4cf9df51afa421deea`, using that shared
revision. This records the tested implementation before the consumer PR's final
documentation review; it is not evidence for later revisions or physical hardware.
