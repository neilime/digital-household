# ADR 0001: Public source and separate deployment domains

Date: 2026-10-28

Status: Accepted planning baseline. Infrastructure deployment remains pending.

## Decision

Publish `neilime/digital-household` as a public repository at the owner's request. Its purpose
is reproducible home infrastructure, reliable home automation and personal AI assistance. Source visibility does not permit publication
of operational data, account credentials or infrastructure state.

Maintain separate professional and personal state, credentials and deployment
approvals. Use Bitwarden for human-managed credentials and recovery keys. Start
from fresh infrastructure; implement Home Assistant features through feature ADRs
when applicable. Qualify the actual disk/network or selected cloud project at
deployment time. Repository and VM-fixture preparation needs no cloud inventory.

## Consequences

Shared CI belongs in `hoverkraft-tech/ci-github-iac`; consumer scenarios belong here.
The initial shared dependency is pinned to a reviewed-in-progress bootstrap commit.
Merge the shared workflow before its consumers and validate any updated pin.
No placeholder state backend, cloud account, production secret or deploy workflow
is introduced to make bootstrap appear complete.
