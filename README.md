# ClamavMirror487

Provision a ClamAV database mirror on Ubuntu with Ansible, Caddy automatic HTTPS,
cvdupdate, and an optional Yandex Cloud DNS TXT advertisement. MIT licensed.

**[English](docs/en/README.md)** · **[Русский](docs/ru/README.md)**

Requirements: Python 3.12+, uv, OpenSSH, an existing sudo administrator, and a target
with the caddy and clamav-cvdupdate packages (tested on Ubuntu 24.04).

```sh
./clamav-mirror inventory --output /private/path/inventory.yml
# Edit the generated placeholders and encrypt any proxy password with Vault.
./clamav-mirror plan
./clamav-mirror apply --verify --no-hooks
./clamav-mirror verify
```

Use --dns when creating the inventory to select the cloud-enabled example. DNS is
disabled by default and is independent of Let's Encrypt certificate issuance.
HTTP and HTTPS both serve files; Range requests are verified after deployment.

The launcher follows MegaProxyServer conventions: inventory-path, external private
inventory, plan/apply/verify, optional post-config-change hooks, and uv.lock dependencies.
It provisions a fresh system; one-off migration scripts do not belong in this repository.

Examples: [basic](inventory.example.yml), [Yandex Cloud DNS](inventory.dns.example.yml).
Client database downloads are public; proxy credentials stay in Vault/private server config.
SSH hardening replaces the administrator's authorized_keys; verify your key first.

```sh
./clamav-mirror check
./clamav-mirror --inventory inventory.example.yml plan --syntax-check
./clamav-mirror --inventory inventory.dns.example.yml plan --syntax-check
```

See [LICENSE](LICENSE).
