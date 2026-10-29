"""Install the real ISO on a disposable disk and validate the installed host."""

import ipaddress
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
from pathlib import Path

import pytest


class ProxmoxGuest:
    """Own only the nested QEMU process and files created for this test."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.source = Path.cwd()
        self.answer = tomllib.loads((self.source / "answer.toml").read_text())
        self.process = None
        self.log = None
        self.ssh_options = [
            "-i",
            str(self.source / "key"),
            "-p",
            "2222",
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "PasswordAuthentication=no",
            "-o",
            "KbdInteractiveAuthentication=no",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={directory}/known_hosts",
        ]

    @staticmethod
    def run(args, timeout=60):
        """Keep failures bounded; raw VM logs and answer contents stay private."""
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        if result.returncode:
            raise RuntimeError(f"{args[0]} failed with exit code {result.returncode}")
        return result.stdout.strip()

    def command(self, command, timeout=60):
        """Execute assertions through the test-only loopback SSH endpoint."""
        return self.run(["ssh", *self.ssh_options, "root@127.0.0.1", command], timeout)

    def install(self):
        """Boot the prepared UEFI ISO and require installer power-off."""
        disk = self.directory / "system.qcow2"
        self.run(["qemu-img", "create", "-f", "qcow2", str(disk), "32G"])
        shutil.copyfile("/usr/share/OVMF/OVMF_VARS_4M.fd", self.directory / "uefi.fd")
        network = self.answer["network"]
        address = ipaddress.ip_interface(network["cidr"])
        mac = ":".join(re.findall("..", network["filter"]["ID_NET_NAME_MAC"][3:]))
        serial = self.answer["disk-setup"]["filter"]["ID_SERIAL"]
        arguments = [
            "qemu-system-x86_64",
            "-machine",
            "q35,accel=kvm",
            "-cpu",
            "host",
            "-smp",
            "2",
            "-m",
            "4096",
            "-display",
            "none",
            "-monitor",
            "none",
            "-drive",
            "if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd",
            "-drive",
            f"if=pflash,format=raw,file={self.directory}/uefi.fd",
            "-drive",
            f"if=none,id=system,format=qcow2,file={disk}",
            "-device",
            f"virtio-blk-pci,drive=system,serial={serial}",
            "-netdev",
            (
                f"user,id=lan,net={address.network},host={network['gateway']},"
                f"dns={network['dns']},dhcpstart={address.ip},"
                f"hostfwd=tcp:127.0.0.1:2222-{address.ip}:22"
            ),
            "-device",
            f"virtio-net-pci,netdev=lan,mac={mac}",
            "-serial",
            f"file:{self.directory}/serial.log",
        ]
        self.log = (self.directory / "qemu.log").open("w", encoding="utf-8")
        # This instance only sees a new regular file, never a host block device.
        # pylint: disable=consider-using-with
        self.process = subprocess.Popen(
            [
                *arguments,
                "-cdrom",
                str(self.source / "autoinstall.iso"),
                "-boot",
                "order=d",
            ],
            stdout=self.log,
            stderr=self.log,
        )
        assert self.process.wait(timeout=900) == 0, "Installer did not power off successfully"
        self.process = subprocess.Popen(
            [*arguments, "-boot", "order=c"],
            stdout=self.log,
            stderr=self.log,
        )
        # Trust on first use is limited to this owned, isolated loopback QEMU endpoint.
        self.wait_for_ssh(first_boot=True)

    def wait_for_ssh(self, first_boot=False, previous_boot=None):
        """Require a running QEMU and a new boot ID when verifying a reboot."""
        deadline = time.monotonic() + 300
        readiness = "for service in pve-cluster pvedaemon pveproxy; do "
        readiness += 'systemctl is-active --quiet "$service" || exit 1; done; '
        readiness += "cat /proc/sys/kernel/random/boot_id"
        while time.monotonic() < deadline:
            assert self.process.poll() is None, "Installed Proxmox VM exited unexpectedly"
            options = ["-o", "StrictHostKeyChecking=accept-new"] if first_boot else []
            result = subprocess.run(
                [
                    "ssh",
                    *options,
                    *self.ssh_options,
                    "root@127.0.0.1",
                    readiness,
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip() != previous_boot:
                return
            time.sleep(5)
        raise TimeoutError("Installed host did not become reachable with its SSH key")

    def baseline(self, check=False):
        """Exercise the deployment playbook, including its actual target preflight."""
        inventory = self.directory / "inventory.json"
        known_hosts = self.directory / "known_hosts"
        ssh_args = f"-o UserKnownHostsFile={known_hosts} -o IdentitiesOnly=yes"
        inventory.write_text(
            json.dumps(
                {
                    "proxmox": {
                        "hosts": {
                            "installed": {
                                "ansible_host": "127.0.0.1",
                                "ansible_port": 2222,
                                "ansible_user": "root",
                                "ansible_ssh_private_key_file": str(self.source / "key"),
                                "ansible_ssh_common_args": ssh_args,
                                "proxmox_expected_fqdn": self.answer["global"]["fqdn"],
                                "proxmox_repository_channel": "no-subscription",
                            }
                        }
                    }
                }
            )
        )
        return self.run(
            [
                "ansible-playbook",
                "-i",
                str(inventory),
                "ansible/proxmox.yml",
                *(["--check"] if check else []),
            ],
            timeout=180,
        )

    def close(self):
        """Stop our child process, including after installer timeout or assertion failure."""
        try:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=15)
            assert self.process is None or self.process.poll() is not None, "QEMU cleanup failed"
        finally:
            if self.log is not None:
                self.log.close()


@pytest.fixture(scope="module", name="guest")
def installed_guest():
    """Allocate a private nested guest only inside the isolated Lima test VM."""
    assert Path("/etc/digital-household-disposable-test").is_file()
    assert os.access("/dev/kvm", os.R_OK | os.W_OK), "Nested KVM is required"
    filesystem = ProxmoxGuest.run(["findmnt", "-n", "-o", "FSTYPE", "--target", str(Path.cwd())])
    assert filesystem not in ("tmpfs", "ramfs"), "VM disks require disk-backed storage"
    with tempfile.TemporaryDirectory(prefix="proxmox-install-", dir=Path.cwd()) as directory:
        machine = ProxmoxGuest(Path(directory))
        try:
            machine.install()
            yield machine
        finally:
            machine.close()


def test_installed_platform_storage_and_management(guest):
    """The ISO produces a bootable UEFI Proxmox host with working local storage and API."""
    version = guest.command("pveversion")
    manifest = json.loads(Path("proxmox/iso.json").read_text(encoding="utf-8"))
    major = manifest["version"].split(".")[0]
    assert version.startswith(f"pve-manager/{major}.")
    assert guest.command("uname -r").endswith("-pve")
    guest.command("test -d /sys/firmware/efi && test -c /dev/kvm")
    assert guest.command("findmnt -n -o FSTYPE /") == "ext4"
    serial = guest.answer["disk-setup"]["filter"]["ID_SERIAL"]
    assert guest.command("lsblk -dn -o SERIAL /dev/vda") == serial
    storage = guest.command("pvesm status")
    assert re.search(r"local\s+dir\s+active", storage)
    assert re.search(r"local-lvm\s+lvmthin\s+active", storage)
    services = guest.command("systemctl is-active pve-cluster pvedaemon pveproxy")
    assert services.splitlines() == ["active"] * 3
    assert "Proxmox" in guest.command("curl --fail --silent --insecure https://127.0.0.1:8006/")


def test_static_network_and_identity(guest):
    """The installed bridge, route and hostname use the supplied synthetic answer."""
    assert guest.command("hostname -f") == guest.answer["global"]["fqdn"]
    assert guest.answer["network"]["cidr"] in guest.command("ip -4 -o addr show dev vmbr0")
    assert f"via {guest.answer['network']['gateway']}" in guest.command("ip -4 route show default")
    guest.command("getent hosts download.proxmox.com")


def test_baseline_is_idempotent_and_survives_reboot(guest):
    """Real host preflight, repository refresh and key-only SSH survive reapplication and reboot."""
    debian_sources = guest.command("sha256sum /etc/apt/sources.list.d/debian.sources")
    guest.baseline()
    for check in (False, True):
        assert re.search(r"changed=0\s+unreachable=0\s+failed=0", guest.baseline(check=check))
    assert guest.command("sha256sum /etc/apt/sources.list.d/debian.sources") == debian_sources
    effective = guest.command("sshd -T").splitlines()
    assert "passwordauthentication no" in effective
    assert "kbdinteractiveauthentication no" in effective
    assert "permitrootlogin without-password" in effective
    guest.command("apt-get update -o APT::Update::Error-Mode=any", timeout=300)
    boot = guest.command("cat /proc/sys/kernel/random/boot_id")
    guest.run(
        [
            "ansible",
            "-i",
            str(guest.directory / "inventory.json"),
            "proxmox",
            "-m",
            "ansible.builtin.reboot",
            "-a",
            "reboot_timeout=300",
        ],
        timeout=360,
    )
    guest.wait_for_ssh(previous_boot=boot)
    assert "passwordauthentication no" in guest.command("sshd -T").splitlines()
    web_check = "curl --retry 12 --retry-connrefused --retry-delay 5"
    web_check += " --fail --silent --insecure https://127.0.0.1:8006/"
    assert "Proxmox" in guest.command(web_check, timeout=90)
    assert re.search(r"changed=0\s+unreachable=0\s+failed=0", guest.baseline(check=True))
