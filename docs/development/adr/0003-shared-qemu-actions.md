# ADR 0003: Shared direct-QEMU actions

Date: 2026-10-31

Status: Proposed; requires shared-action and consumer CI qualification before merge.

## Context

[ADR 0002](0002-proxmox-installation-runner.md) chose direct QEMU after the nested
Lima scenario timed out on hosted runners. The direct implementation passed
[hosted CI](https://github.com/neilime/digital-household/actions/runs/40979527334),
but left reusable VM lifecycle and report publication in the consumer.

## Decision

Keep direct QEMU and move its lifecycle into `ci-github-iac`'s existing create,
test and destroy actions. The consumer prepares synthetic installation inputs,
selects explicit VM resources and retains Proxmox assertions. Tests execute on
the runner against the private SSH configuration supplied by the shared action.
The shared test action owns report collection, parsing, comments and artifacts.

## Consequences

This supersedes the consumer-owned Docker/QEMU lifecycle in ADR 0002. ISO tooling
still runs in its pinned container. QEMU dependencies come from the shared setup
action, and pytest/Ansible use a temporary runner virtual environment. Changes
require a shared release; the three VM actions must use the same immutable pin.
Real hardware and Home Assistant qualification remain separate acceptance tasks.
