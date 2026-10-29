# Make and workflow conventions

Follow the [workstation-manager Makefile](https://github.com/neilime/workstation-manager/blob/main/Makefile)
and [workflow layout](https://github.com/neilime/workstation-manager/tree/main/.github/workflows).
Use annotated targets for `make help` and a shared `run_linter` helper for
`make lint` and `make lint-fix`. The linter runs on Linux amd64 with the caller's
UID/GID and the checkout's absolute path as its workspace. A failed image build
stops the command before linting. The shared image respects `.gitignore`; keep
local caches and generated reports excluded there.

`make lint-fix` applies supported automatic fixes. `make lint docs/` limits
linting to matching paths. Positional filters apply only to lint commands;
unknown standalone targets fail. `make ci` runs linting with fixes, installer
tests, Ansible syntax checks and a baseline test in a disposable container.
CI executes `tests/proxmox-test.yml` through the shared Ansible test action; the
playbook reuses the same disposable-container assertions and publishes native
JUnit reports. Ansible Lint stays in the separate linter job.
VM integration tests run in CI; see the
[validation guide](docs/usage/validation.md) for scenarios and reporting.
The Proxmox end-to-end job uses the shared VM actions to isolate a real unattended
installation, then runs pytest inside that guest. Keep the pytest pin in
`tests/proxmox/requirements.txt`; Dependabot updates it with the tooling Python
requirements. Keep workflow scripting in adjacent GitHub Script modules.

`main-ci.yml` and `pull-request-ci.yml` call `shared-ci.yml`. Main supports
pushes and manual runs; PR CI also supports merge queues. Both cancel superseded
runs for the same workflow and ref. Start workflows with `permissions: {}` and
grant only the permissions required by each job. Keep step names descriptive and
Actions pinned. Compose shared VM operations in the job, and review each job's
result before merging.

Use Conventional Commits and reviewed pull requests. Pin all three VM actions
to the same immutable revision in `shared-ci.yml`. Update those references
together when adopting a shared CI change, then require the hosted VM job to pass
before merging.

## Repository automation

Keep the five Hoverkraft maintenance workflows alongside the CI entrypoints:

- `greetings.yml` welcomes first-time contributors on new issues and PRs.
- `need-fix-to-issue.yml` turns fix markers into issues after main pushes, or
  for a manually selected commit range.
- `semantic-pull-request.yml` validates Conventional Commit PR titles.
- `renovate.yml` runs dependency updates weekly and on manual dispatch.
- `stale.yml` manages inactive issues and PRs daily using shared defaults.

The four collaboration workflows reuse pinned ci-github-common workflows.
Renovate uses the repository's built-in `GITHUB_TOKEN`, scoped through job
permissions. No additional credential is required. Keep the repository
configuration in `.github/renovate.json`. Dependabot owns Actions, Docker
and Python requirements updates, including the tooling image. All version updates
are grouped per ecosystem, following workstation-manager. Renovate handles the
pinned Proxmox assistant Debian package, Ansible collections and Terraform
dependencies. Docker updates are disabled in Renovate to avoid duplicate ownership.

Review Proxmox installer releases manually against the
[official download page](https://www.proxmox.com/en/downloads/proxmox-virtual-environment).
Update the version, URL and SHA-256 together in `proxmox/iso.json`, then prepare
an ISO with synthetic settings before reviewing the change. Treat changes to the
Proxmox archive-key checksum as a separate trust review. Keep pins in manifests,
not copied version numbers in usage guides.

Enable "Allow GitHub Actions to create and approve pull requests" under
Settings > Actions > General so Renovate can open PRs. GitHub couples creation
and approval in this setting; the workflows do not approve PRs or enable
automatic merges. Obtain the required review and verify CI results before merging.
For a Renovate PR, select "Approve workflows to run" on the PR page to start
its pending CI runs, then review the results and changes before merging.
See [GitHub's token-trigger rules](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs).
