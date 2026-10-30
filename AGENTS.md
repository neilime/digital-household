# Repository instructions

- Follow the [Make and workflow conventions](CONTRIBUTING.md)
  from workstation-manager and Hoverkraft when changing tooling.
- This public repository belongs to `neilime` and owns Proxmox, Home Assistant, personal services and family integrations.
- Keep infrastructure state, credentials, private inventory and user data out of Git.
  Use domain-specific credentials; never share professional and personal identities.
- Keep secrets in Bitwarden for human custody. Deployment automation receives only
  narrowly scoped credentials from a protected environment when implemented.
- Compose pinned Hoverkraft VM actions for Linux guest tests. The Proxmox installer
  runs directly in QEMU inside a disposable container on the runner, avoiding an
  extra Lima layer. Keep scenario assertions here and always schedule cleanup.
- Use `actions/github-script` for workflow scripting, matching the shared actions.
- Run `make lint` after edits and the relevant disposable tests for behavior changes.
  Use synthetic data. Never execute a host-changing test on the developer workstation.
- Keep deployment commands unavailable until an actual implementation and point-of-use
  preflight exist. Production changes require environment approval.
- Keep root readme for end users, detailed guides in docs/ and decisions in ADRs.
  Use Conventional Commits and reviewed pull requests.
