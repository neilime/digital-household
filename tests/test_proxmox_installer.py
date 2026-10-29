"""Protect target selection, private outputs and image integrity before installation."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.proxmox_installer import Installer


class InstallerTests(unittest.TestCase):
    """Exercise the native answer validator and safe media preparation boundaries."""

    def setUp(self):
        # unittest owns this context until cleanup, including when a test fails.
        # pylint: disable-next=consider-using-with
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.answer = self.root / "answer.toml"
        self.valid = (Path(__file__).parent / "fixtures/proxmox-answer.toml").read_text()
        self.answer.write_text(self.valid)
        self.answer.chmod(0o600)
        self.iso = self.root / "source.iso"
        self.iso.write_bytes(b"synthetic image bytes")
        self.manifest = self.root / "iso.json"
        self.manifest.write_text(
            json.dumps(
                {
                    "url": self.iso.as_uri(),
                    "sha256": hashlib.sha256(self.iso.read_bytes()).hexdigest(),
                }
            )
        )
        self.installer = Installer(self.manifest)

    def test_exact_private_answer_passes_native_validation(self):
        """The supported answer schema remains accepted by the native assistant."""
        self.installer.validate_answer(self.answer)

    def test_ambiguous_or_unsafe_answers_are_rejected(self):
        """Reject broad selectors, wrong types and unsupported installation policies."""
        cases = [
            ('"SYNTHETIC_INSTALLATION_DISK"', '"*"'),
            ('"all"', '"any"'),
            ('filesystem = "ext4"', 'filesystem = "ext4"\ndisk-list = ["sda"]'),
            ('source = "from-answer"', 'source = "from-dhcp"'),
            ('"enx020000000001"', '"enx*"'),
            ('gateway = "192.0.2.1"', 'gateway = "198.51.100.1"'),
            ('reboot-mode = "power-off"', 'reboot-mode = "reboot"'),
            ("[global]", '[global]\nroot-password = "synthetic plaintext"'),
            ('country = "fr"', 'country = "REPLACE_WITH_COUNTRY"'),
            ('fqdn = "pve.example.invalid"', 'fqdn = "hostonly"'),
            (
                'filter.ID_SERIAL = "SYNTHETIC_INSTALLATION_DISK"',
                "filter.ID_SERIAL = 42",
            ),
            ("[global]", 'network = "wrong type"\n[global]'),
        ]
        for before, after in cases:
            with self.subTest(change=before):
                self.answer.write_text(self.valid.replace(before, after))
                with self.assertRaises(ValueError):
                    self.installer.validate_answer(self.answer)

    def test_public_answer_and_symlink_are_rejected(self):
        """Private answer files cannot be public or redirected through a symlink."""
        self.answer.chmod(0o644)
        with self.assertRaises(ValueError):
            self.installer.validate_answer(self.answer)
        self.answer.chmod(0o600)
        link = self.root / "link.toml"
        link.symlink_to(self.answer)
        with self.assertRaises(ValueError):
            self.installer.validate_answer(link)

    def test_malformed_answer_does_not_expose_input_in_error(self):
        """Syntax errors never echo potentially private answer values."""
        self.answer.write_text('root-password = "PRIVATE_TEST_SENTINEL\n')
        with self.assertRaises(ValueError) as raised:
            self.installer.validate_answer(self.answer)
        self.assertNotIn("PRIVATE_TEST_SENTINEL", str(raised.exception))

    def test_checksum_failure_keeps_existing_source(self):
        """A corrupt existing cache is reported and preserved for inspection."""
        self.iso.write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            self.installer.download(self.iso)
        self.assertEqual(self.iso.read_bytes(), b"corrupt")

    def test_download_verifies_bytes_before_publishing(self):
        """Only downloads with the reviewed checksum reach the requested path."""
        cached = self.root / "cache/image.iso"
        self.installer.download(cached)
        self.assertEqual(cached.read_bytes(), self.iso.read_bytes())
        self.iso.write_bytes(b"corrupt")
        rejected = self.root / "cache/rejected.iso"
        with self.assertRaises(ValueError):
            self.installer.download(rejected)
        self.assertFalse(rejected.exists())

    def test_prepare_refuses_to_replace_existing_output(self):
        """Preparing media never overwrites an existing output."""
        output = self.root / "existing.iso"
        output.write_bytes(b"keep me")
        with self.assertRaises(ValueError):
            self.installer.prepare(self.answer, self.iso, output)
        self.assertEqual(output.read_bytes(), b"keep me")

    def test_failed_preparation_does_not_publish_partial_media(self):
        """A native preparation failure removes staging files and publishes nothing."""
        output = self.root / "private/prepared.iso"
        with (
            patch.object(Installer, "validate_answer"),
            patch(
                "scripts.proxmox_installer.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, ["installer"]),
            ),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            self.installer.prepare(self.answer, self.iso, output)
        self.assertFalse(output.exists())
        self.assertEqual(list(output.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
