"""Install the real ISO on a disposable disk and validate the installed host."""

import json
import os
import re
import subprocess
import tempfile
import time
import tomllib
from pathlib import Path

import pytest


class ProxmoxGuest:
    """Assert the installed platform through the shared VM action's SSH configuration."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.answer = tomllib.loads(
            Path(os.environ["E2E_DIRECTORY"], "answer.toml").read_text(encoding="utf-8")
        )
        self.ssh_config = os.environ["VM_SSH_CONFIG"]
        self.ssh_options = ["-F", self.ssh_config]

    @staticmethod
    def run(args, timeout=60):
        """Keep failures bounded; raw VM logs and answer contents stay private."""
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        if result.returncode:
            raise RuntimeError(f"{args[0]} failed with exit code {result.returncode}")
        return result.stdout.strip()

    def command(self, command, timeout=60):
        """Execute assertions through the test-only loopback SSH endpoint."""
        return self.run(["ssh", *self.ssh_options, "iac-test", command], timeout)

    def wait_for_ssh(self, previous_boot=None):
        """Require platform readiness and a new boot ID when verifying a reboot."""
        deadline = time.monotonic() + 300
        readiness = "for service in pve-cluster pvedaemon pveproxy; do "
        readiness += 'systemctl is-active --quiet "$service" || exit 1; done; '
        readiness += "cat /proc/sys/kernel/random/boot_id"
        while time.monotonic() < deadline:
            result = subprocess.run(
                [
                    "ssh",
                    *self.ssh_options,
                    "iac-test",
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
        ssh_args = f"-F {self.ssh_config}"
        inventory.write_text(
            json.dumps(
                {
                    "proxmox": {
                        "hosts": {
                            "installed": {
                                "ansible_host": "iac-test",
                                "ansible_user": "root",
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


@pytest.fixture(scope="module", name="guest")
def installed_guest():
    """Use only the disposable guest explicitly supplied by the shared VM actions."""
    config = Path(os.environ["VM_SSH_CONFIG"])
    runtime = Path(os.environ["VM_DIRECTORY"])
    assert runtime.parent == Path("/var/tmp")
    assert runtime.name.startswith(f"iac-qemu-{os.getuid()}-")
    assert config == runtime / "ssh.config" and config.is_file()
    with tempfile.TemporaryDirectory(prefix="proxmox-assertions-") as directory:
        machine = ProxmoxGuest(Path(directory))
        machine.wait_for_ssh()
        yield machine


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
