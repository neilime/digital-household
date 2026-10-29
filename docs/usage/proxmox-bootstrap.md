# Bootstrap the UM690 with Proxmox

Prepare an unattended Proxmox installation and apply the host baseline from a
Linux workstation with Docker, GNU Make and OpenSSH. Allow 6 GB of free space
for the source ISO, temporary files and prepared media. The supported target is
a standalone Proxmox VE 9 host on Debian 13, with one ext4 installation disk,
wired Ethernet and static IPv4 management networking.

The installer erases the selected disk when booted. Preparing an ISO does not
authorize erasing a machine. Confirm the actual disk, saved data and intended
network settings at the UM690 console before booting unattended media.

## Identify the actual target

Connect a screen, keyboard and wired Ethernet. Disconnect unrelated storage.
Use the unmodified official installer in its diagnostic/debug shell, or a Linux
live environment, to inspect the hardware without starting installation:

```sh
lsblk -d -o NAME,MODEL,SIZE,SERIAL
ip -br link
```

For the chosen disk and connected interface, substitute their actual names:

```sh
udevadm info --query=property --name=/dev/nvme0n1
udevadm info --query=property --path=/sys/class/net/enp1s0
```

Record the complete disk `ID_SERIAL` and interface `ID_NET_NAME_MAC` values.
The interface value has the form `enx` followed by twelve lowercase MAC digits.
Do not derive a filter from a shortened disk serial or a guessed interface name.
If a required property is absent, stop and review the hardware selection.

Where the native assistant is installed on the target, `device-info` shows the
available properties. `device-match disk 'ID_SERIAL=ACTUAL_VALUE'` and
`device-match network 'ID_NET_NAME_MAC=ACTUAL_VALUE'` must each select exactly one
intended device. Run these subcommands through `proxmox-auto-install-assistant`
on the UM690, not in the workstation tooling container.

Prepare an unused LAN address/prefix, gateway, resolver and fully qualified
hostname. Reserve the address outside the DHCP pool and configure local DNS.
Keep management ports on the trusted LAN without internet port forwarding.

## Prepare private installation media

From the repository root:

```sh
umask 077
mkdir -p .local/proxmox
cp proxmox/answer.example.toml .local/proxmox/answer.toml
chmod 600 .local/proxmox/answer.toml
```

Edit the private copy and replace every `REPLACE_` value. Keep the personal
root password in Bitwarden. Generate its SHA-512 hash with `openssl passwd -6`,
which prompts for the password; place only the resulting hash in the answer.
Add the public half of a dedicated Ed25519 SSH key. Keep the private key outside
the checkout, protected by the personal credential policy. Never put a password
or private key in shell arguments, Git, a workflow log or chat.

Keep `reboot-mode = "power-off"`: remove the installation USB after completion
before starting the installed host. Booting the unattended media again can
reinstall the machine.

```sh
make proxmox-answer-check
make proxmox-download
make proxmox-iso
```

The download is accepted only when its full SHA-256 matches
[the committed manifest](../../proxmox/iso.json). The default cache is
`.cache/proxmox/installer.iso`; a corrupt cache fails rather than being replaced.
The official download transport is HTTP; integrity depends on the reviewed
checksum from the official release page. Do not change the checksum merely to
accept a failed download.

The native assistant validates the answer and embeds it in
`.local/proxmox/autoinstall.iso`. The wrapper requires a private answer file,
an exact disk serial and NIC selector, a password hash and an SSH public key.
Native diagnostics are suppressed because they may contain private answer data.
No command writes a block device. Existing output is preserved; set a new
`OUTPUT=.local/proxmox/another.iso` when rebuilding. `ANSWER` and `ISO` can also
select other paths within the checkout.

Treat both the answer and prepared ISO as sensitive: the image contains the
password hash, network details and public administration key. Keep them local,
never attach them to a PR or public CI artifact, and remove them after installation
when no longer needed. The original public ISO may remain cached.

## Install and verify at the console

1. Reconfirm the disk identity, any data that must be saved, and permission to erase it.
2. Flash the prepared ISO to a verified spare USB using the
   [official installation-media procedure](https://github.com/proxmox/pve-docs/blob/master/pve-installation-media.adoc).
   Flashing overwrites that USB drive.
3. Enable hardware virtualization in firmware and boot the USB on the UM690.
   The prepared image selects unattended installation automatically; do not boot
   it on another machine or leave it inserted after installation.
4. After the installer powers off, remove the USB and boot from the internal disk.
5. Verify the disk/storage layout, hostname, LAN address, DNS, gateway and time.
   Check `pveversion` and access `https://MANAGEMENT_ADDRESS:8006` from the trusted
   LAN as `root@pam`. Match the address and certificate against the console.

An exact filter limits selection; it cannot establish that a selected disk is
safe to erase. Console verification remains required.

## Preview and apply the host baseline

Copy [the inventory example](../../ansible/inventory.example.yml) to
`.local/proxmox/inventory.yml` and replace its placeholders with the installed
host's address and FQDN. Select `enterprise` if the node has a subscription;
otherwise select `no-subscription`. Enterprise is the upstream recommendation
for production; the no-subscription packages receive less extensive testing.

At the host console, obtain the SSH host-key fingerprint with
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Collect that host's public key
into a dedicated local `known_hosts` file and compare its fingerprint with the
console before trusting it. `ssh-keyscan` alone does not authenticate a host.

Keep the console available and verify key-based root SSH access. Then preview:

```sh
make proxmox-plan \
  INVENTORY=.local/proxmox/inventory.yml \
  SSH_KEY=/absolute/path/to/personal-proxmox-key \
  KNOWN_HOSTS=/absolute/path/to/verified-known-hosts
```

The tooling uses strict host-key checking and disables password fallback.
Its SSH client cannot prompt to unlock a key; use an explicitly prepared,
protected automation identity. It mounts only the named key and known-hosts
files. Do not pass an entire personal SSH directory or an agent into the container.

Review the preview against the console and approve this host change at the point
of use. To apply, run the same command with `proxmox-configure`. Automated
production deployments must use the protected `production` environment; no
deployment workflow is included here.

The playbook checks Debian/Proxmox versions, FQDN, an installed administration
key and absence of cluster/Ceph configuration. It selects the APT channel,
removes the installer's enterprise/Ceph source entries, and configures key-only
SSH with password login and agent/X11 forwarding disabled. Debian sources are
preserved. The root password remains available for the console and web UI.

Open a second SSH connection before closing the first. Re-run `proxmox-plan`:
an unchanged host should report no changes. Refresh packages in the Proxmox UI,
review available updates and perform any upgrade/reboot with console access.
This baseline does not upgrade packages, change the firewall, create VMs or
configure backups. Keep the management interface on the trusted LAN.

## Acceptance and recovery

- [ ] Installation completes on the intended disk and the host boots without the USB.
- [ ] RAM, disk capacity and KVM availability match the UM690 inventory.
- [ ] Web UI and key-based SSH remain reachable after a reboot.
- [ ] DNS, static addressing and the chosen APT channel work.
- [ ] Baseline preview reports no changes after application.
- [ ] Console access and personal Bitwarden credential references are recorded privately.

If preparation fails, correct the private answer or obtain a verified original
ISO and use a new output path. If installation fails, inspect the console before
retrying; never relax a disk selector to make it proceed. If SSH configuration
prevents access, use the local console to inspect/remove only
`/etc/ssh/sshd_config.d/00-digital-household.conf`, validate with `sshd -t`, and
reload `ssh`. Investigate the effective configuration before reapplying.

Host installation and this baseline are prerequisites for the HAOS stack.
HAOS deployment, restore tests and physical-device acceptance remain separate
Phase 2 work. See [validation scope](validation.md) for what CI actually tests.

Upstream references: [automated installation](https://pve.proxmox.com/wiki/Automated_Installation),
[installer implementation](https://github.com/proxmox/pve-installer), and
[package repositories](https://github.com/proxmox/pve-docs/blob/master/pve-package-repos.adoc).
