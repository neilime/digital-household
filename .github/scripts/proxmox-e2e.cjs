const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

exports.prepare = async ({ core, exec, io }) => {
	const parent = path.resolve(".local");
	await io.mkdirP(parent);
	fs.chmodSync(parent, 0o700);
	const directory = fs.mkdtempSync(path.join(parent, "proxmox-e2e-"));
	core.setOutput("directory", path.relative(process.cwd(), directory));
	await exec.exec("ssh-keygen", [
		"-q",
		"-t",
		"ed25519",
		"-N",
		"",
		"-f",
		`${directory}/key`,
	]);
	const key = fs.readFileSync(`${directory}/key.pub`, "utf8").trim();
	const { stdout } = await exec.getExecOutput(
		"openssl",
		["passwd", "-6", "-stdin"],
		{
			input: Buffer.from(crypto.randomBytes(32).toString("hex")),
			silent: true,
		},
	);
	const hash = stdout.trim();
	const answer = fs
		.readFileSync("tests/fixtures/proxmox-answer.toml", "utf8")
		.replace(/^root-password-hashed = .*$/m, `root-password-hashed = "${hash}"`)
		.replace(/^root-ssh-keys = .*$/m, `root-ssh-keys = ["${key}"]`)
		.replace(/^dns = .*$/m, 'dns = "192.0.2.2"')
		.replace(/^filter.ID_SERIAL = .*$/m, 'filter.ID_SERIAL = "PVE_E2E_DISK"');
	const manifest = JSON.parse(fs.readFileSync("proxmox/iso.json", "utf8"));
	fs.writeFileSync(
		`${directory}/goss-vars.json`,
		JSON.stringify({
			major: manifest.version.split(".")[0],
			fqdn: answer.match(/^fqdn = "([^"]+)"/m)[1],
			cidr: answer.match(/^cidr = "([^"]+)"/m)[1],
			gateway: answer.match(/^gateway = "([^"]+)"/m)[1],
			disk_serial: "PVE_E2E_DISK",
		}),
		{ mode: 0o600, flag: "wx" },
	);
	const relative = path.relative(process.cwd(), directory);
	const config = {
		cpus: 2,
		memoryMiB: 4096,
		diskGiB: 32,
		diskSerial: "PVE_E2E_DISK",
		iso: `${relative}/autoinstall.iso`,
		network: {
			subnet: "192.0.2.0/24",
			address: "192.0.2.10",
			gateway: "192.0.2.1",
			dns: "192.0.2.2",
			mac: "02:00:00:00:00:01",
		},
		ssh: { user: "root", privateKey: `${relative}/key` },
	};
	fs.writeFileSync(`${directory}/vm.json`, JSON.stringify(config), {
		mode: 0o600,
		flag: "wx",
	});
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

exports.cleanup = async ({ io }) => {
	await io.rmRF(fixtureDirectory());
};
