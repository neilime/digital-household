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

function fixtureDirectory() {
	const directory = path.resolve(process.env.E2E_DIRECTORY || "");
	if (
		path.dirname(directory) !== path.resolve(".local") ||
		!/^proxmox-e2e-[a-zA-Z0-9]+$/.test(path.basename(directory))
	) {
		throw new Error("Refusing access outside this test's private directory");
	}
	return directory;
}

async function stage(exec, directory) {
	// Copy an explicit allowlist. Never mount the checkout or copy private local inventory.
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
		{
			input: files,
		},
	);
	await exec.exec("tar", ["-xf", `${directory}/source.tar`, "-C", directory]);
	fs.unlinkSync(`${directory}/source.tar`);
}

exports.run = async ({ exec, core }) => {
	const directory = fixtureDirectory();
	const kvm = fs.statSync("/dev/kvm");
	if (!kvm.isCharacterDevice())
		throw new Error("A KVM-capable runner is required");
	await stage(exec, directory);
	try {
		await exec.exec("docker", [
			"run",
			"--name",
			path.basename(directory),
			"--init",
			"--device=/dev/kvm",
			"--group-add",
			String(kvm.gid),
			"--user",
			`${process.getuid()}:${process.getgid()}`,
			"--cap-drop=ALL",
			"--security-opt=no-new-privileges",
			"--mount",
			`type=bind,src=${directory},dst=/var/tmp/proxmox-e2e`,
			"digital-household-proxmox-test:local",
		]);
	} finally {
		for (const [output, file] of Object.entries({
			report: "reports/proxmox.xml",
			console: "diagnostics/installer.png",
		})) {
			const filename = path.join(directory, file);
			if (fs.existsSync(filename)) core.setOutput(output, filename);
		}
	}
};

exports.cleanup = async ({ exec }) => {
	const directory = fixtureDirectory();
	const name = path.basename(directory);
	const { stdout } = await exec.getExecOutput("docker", [
		"container",
		"ls",
		"--all",
		"--filter",
		`name=^/${name}$`,
		"--format={{.ID}}",
	]);
	if (stdout.trim()) await exec.exec("docker", ["rm", "--force", name]);
	fs.rmSync(directory, { recursive: true, force: true });
};
