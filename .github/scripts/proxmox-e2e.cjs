const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { execFileSync } = require("node:child_process");

exports.prepare = ({ core }) => {
	const parent = path.resolve(".local");
	fs.mkdirSync(parent, { recursive: true, mode: 0o700 });
	const directory = fs.mkdtempSync(path.join(parent, "proxmox-e2e-"));
	core.setOutput("directory", path.relative(process.cwd(), directory));
	execFileSync("ssh-keygen", [
		"-q",
		"-t",
		"ed25519",
		"-N",
		"",
		"-f",
		`${directory}/key`,
	]);
	const key = fs.readFileSync(`${directory}/key.pub`, "utf8").trim();
	const hash = execFileSync("openssl", ["passwd", "-6", "-stdin"], {
		input: crypto.randomBytes(32).toString("hex"),
		encoding: "utf8",
	}).trim();
	const answer = fs
		.readFileSync("tests/fixtures/proxmox-answer.toml", "utf8")
		.replace(/^root-password-hashed = .*$/m, `root-password-hashed = "${hash}"`)
		.replace(/^root-ssh-keys = .*$/m, `root-ssh-keys = ["${key}"]`)
		.replace(/^dns = .*$/m, 'dns = "192.0.2.2"')
		.replace(/^filter.ID_SERIAL = .*$/m, 'filter.ID_SERIAL = "PVE_E2E_DISK"');
	fs.writeFileSync(`${directory}/answer.toml`, answer, {
		mode: 0o600,
		flag: "wx",
	});
};

exports.stage = async ({ exec }) => {
	const name = process.env.VM_NAME;
	const directory = process.env.E2E_DIRECTORY;
	// Copy an explicit allowlist. Never mount the checkout or copy private local inventory.
	await exec.exec("limactl", [
		"shell",
		"--workdir=/tmp",
		name,
		"mkdir",
		"-m",
		"700",
		"/tmp/proxmox-e2e",
	]);
	const files = execFileSync("git", [
		"ls-files",
		"--cached",
		"--others",
		"--exclude-standard",
		"-z",
		"--",
		"ansible",
		"proxmox",
		"scripts/proxmox_installer.py",
		"tests/proxmox",
		"docker/tooling/requirements.txt",
	]);
	await exec.exec(
		"tar",
		["-cf", `${directory}/source.tar`, "--null", "-T", "-"],
		{ input: files },
	);
	for (const file of ["source.tar", "answer.toml", "key", "autoinstall.iso"]) {
		await exec.exec("limactl", [
			"copy",
			`${directory}/${file}`,
			`${name}:/tmp/proxmox-e2e/${file}`,
		]);
	}
	await exec.exec("limactl", [
		"shell",
		"--workdir=/tmp/proxmox-e2e",
		name,
		"tar",
		"-xf",
		"source.tar",
	]);
};

exports.cleanup = () => {
	const directory = path.resolve(process.env.E2E_DIRECTORY);
	if (
		path.dirname(directory) !== path.resolve(".local") ||
		!path.basename(directory).startsWith("proxmox-e2e-")
	) {
		throw new Error("Refusing cleanup outside this test's private directory");
	}
	fs.rmSync(directory, { recursive: true, force: true });
};
