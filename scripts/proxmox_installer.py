#!/usr/bin/env python3
"""Validate the private installation answer and prepare a verified Proxmox ISO."""

import argparse
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import tempfile
import tomllib
from pathlib import Path
from urllib.request import urlopen


class Installer:
    """Keep image integrity and installation-target checks together."""

    def __init__(self, manifest: Path):
        self.image = json.loads(manifest.read_text())

    @staticmethod
    def validate_answer(answer: Path) -> None:
        """Reject ambiguous targets and plaintext credentials before native validation."""
        if not answer.is_file() or answer.is_symlink():
            raise ValueError("Answer must be a regular, non-symlink file")
        if answer.stat().st_mode & 0o077:
            raise ValueError("Answer must be private: chmod 600 the answer file")
        raw = answer.read_text()
        if "REPLACE_" in raw:
            raise ValueError("Replace all example values in the private answer file")
        try:
            config = tomllib.loads(raw)
        except tomllib.TOMLDecodeError:
            raise ValueError("Answer is not valid TOML") from None
        # Validate the native schema and value types before applying our target policy.
        result = subprocess.run(
            ["proxmox-auto-install-assistant", "validate-answer", str(answer)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode:
            raise ValueError(
                "Proxmox rejected the answer; review its documented fields privately"
            )
        Installer.validate_access(config["global"])
        Installer.validate_disk(config["disk-setup"])
        Installer.validate_network(config["network"])

    @staticmethod
    def validate_access(general: dict) -> None:
        """Require key administration, a password hash, and removal of boot media."""
        if "." not in general.get("fqdn", ""):
            raise ValueError("Provide a fully qualified management hostname")
        if "root-password" in general or not re.fullmatch(
            r"\$(?:6|y)\$[^\s]+", general.get("root-password-hashed", "")
        ):
            raise ValueError("Provide a SHA-512 or yescrypt root password hash only")
        keys = general.get("root-ssh-keys", [])
        if not keys or not all(key.startswith("ssh-ed25519 ") for key in keys):
            raise ValueError(
                "Provide an Ed25519 SSH public key for key-only administration"
            )
        if general.get("reboot-mode") != "power-off":
            raise ValueError(
                "Installation must power off so installation media can be removed"
            )

    @staticmethod
    def validate_disk(disk: dict) -> None:
        """Require an exact installation disk selector."""
        filters = disk.get("filter", {})
        serial = filters.get("ID_SERIAL", "")
        if (
            disk.get("filesystem") != "ext4"
            or "disk-list" in disk
            or disk.get("filter-match") != "all"
            or set(filters) != {"ID_SERIAL"}
            or not isinstance(serial, str)
            or not serial
            or any(char in serial for char in "*?[]")
        ):
            raise ValueError("Select one ext4 installation disk by its exact ID_SERIAL")

    @staticmethod
    def validate_network(network: dict) -> None:
        """Require an exact wired interface and static management addressing."""
        nic = network.get("filter", {})
        if network.get("source") != "from-answer" or set(nic) != {"ID_NET_NAME_MAC"}:
            raise ValueError(
                "Use static networking with an exact ID_NET_NAME_MAC filter"
            )
        if not isinstance(nic["ID_NET_NAME_MAC"], str) or not re.fullmatch(
            r"enx[0-9a-f]{12}", nic["ID_NET_NAME_MAC"]
        ):
            raise ValueError(
                "ID_NET_NAME_MAC must be enx followed by the twelve MAC hex digits"
            )
        try:
            address = ipaddress.ip_interface(network["cidr"])
            gateway = ipaddress.ip_address(network["gateway"])
            ipaddress.ip_address(network["dns"])
        except (KeyError, ValueError):
            raise ValueError(
                "Provide a valid management CIDR, gateway and DNS address"
            ) from None
        if (
            address.version != 4
            or gateway not in address.network
            or gateway == address.ip
        ):
            raise ValueError(
                "Use an IPv4 management address with a separate gateway in its subnet"
            )

    def verify_image(self, iso: Path) -> None:
        """Verify the complete image before using an existing or downloaded file."""
        if not iso.is_file() or iso.is_symlink():
            raise ValueError("ISO must be a regular, non-symlink file")
        with iso.open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != self.image["sha256"]:
            raise ValueError("ISO SHA-256 does not match the reviewed manifest")

    def download(self, iso: Path) -> None:
        """Cache only bytes that match the committed checksum."""
        if iso.exists() or iso.is_symlink():
            self.verify_image(iso)
            return
        iso.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=iso.parent) as temporary:
            downloaded = Path(temporary) / "download.iso"
            with urlopen(self.image["url"], timeout=60) as source, downloaded.open(
                "wb"
            ) as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
            self.verify_image(downloaded)
            downloaded.rename(iso)

    def prepare(self, answer: Path, iso: Path, output: Path) -> None:
        """Create private installation media without touching a physical device."""
        self.validate_answer(answer)
        self.verify_image(iso)
        if output.exists() or output.is_symlink():
            raise ValueError("Output already exists; choose a new private ISO path")
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
            prepared = Path(temporary) / "autoinstall.iso"
            subprocess.run(
                [
                    "proxmox-auto-install-assistant",
                    "prepare-iso",
                    str(iso),
                    "--fetch-from",
                    "iso",
                    "--answer-file",
                    str(answer),
                    "--output",
                    str(prepared),
                    "--tmp",
                    temporary,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            prepared.chmod(0o600)
            prepared.rename(output)


def main() -> None:
    """Run the requested operation with restrictive permissions and bounded errors."""
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("validate", "download", "prepare"))
    parser.add_argument("--answer", type=Path)
    parser.add_argument("--iso", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    required = {
        "validate": ("answer",),
        "download": ("iso",),
        "prepare": ("answer", "iso", "output"),
    }
    if any(getattr(args, key) is None for key in required[args.operation]):
        parser.error(
            f"{args.operation} requires: {', '.join(required[args.operation])}"
        )
    installer = Installer(Path(__file__).resolve().parents[1] / "proxmox/iso.json")
    try:
        if args.operation == "validate":
            installer.validate_answer(args.answer)
        elif args.operation == "download":
            installer.download(args.iso)
        else:
            installer.prepare(args.answer, args.iso, args.output)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Native tools can include answer values in diagnostics. Never relay that output.
        parser.exit(
            1,
            f"Installer operation failed: {error if isinstance(error, ValueError) else type(error).__name__}\n",
        )
    print(f"Proxmox installer {args.operation} completed")


if __name__ == "__main__":
    main()
