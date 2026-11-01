# ClamavMirror487 guide

[Overview](../../README.md) · [Русский](../ru/README.md)

## Commands

| Command | Behavior |
|---|---|
| inventory --output PATH [--dns] | Create private example inventory and inventory-path; refuse overwrite |
| deps | Install locked local dependencies and list Ansible collections |
| plan | Check mode, no automatic diff |
| apply --verify | Apply → verify → hooks; stop on error |
| apply | Apply → hooks |
| verify | Check services, HTTP/HTTPS Range, certificate trust, and enabled DNS via API |
| update | Run the serialized update service immediately |
| vault ARGS | Forward arguments/stdin to ansible-vault |
| check | Local unit tests and Ansible smoke check |

--inventory PATH and --limit HOST work like MegaProxyServer. --no-hooks skips hooks
without disabling verify. --tags/--skip-tags/--start-at-task on apply do not limit
verification; other Ansible arguments are retained. Deployment roles have no tags.
Without --inventory, inventory-path is read, then inventory.yml. Relative paths are
resolved from the repository root. All hosts are applied in parallel unless limited.

## Inventory

Use the native Ansible group clamav_mirrors. Set ansible_user and mirror_admin.user
to an existing non-root administrator with sudo; mirror_admin.public_key becomes its
sole authorized key. Bootstrap through root is not implemented. Debian-family targets
must provide caddy and clamav-cvdupdate; Ubuntu 24.04 is tested.

| Variable | Meaning |
|---|---|
| mirror_domain | Public hostname with DNS pointing at this server; required |
| mirror_email | ACME contact email |
| mirror_home | Updater home/state; default /var/lib/clamav-mirror |
| mirror_webroot | Public database directory; default /var/lib/clamav-mirror/database |
| mirror_update_interval | systemd duration; default 30min |
| mirror_proxy | Empty mapping for direct downloads, or host/login/password for HTTPS proxy |
| mirror_dns.enabled | false by default; enables Yandex Cloud TXT publication |
| mirror_dns.zone_id, record_name, ttl | Existing zone, full TXT name, TTL (default 300) |
| mirror_unattended_upgrades | Periodic security updates; automatic reboot remains disabled |

Set mirror_domain explicitly even when invoking standalone verify. Proxy host is
host[:port], without scheme or credentials. Store password as inline !vault. The
updater percent-encodes credentials; only database downloads use this proxy. Metadata
and Yandex control-plane requests go directly with timeouts.

For existing Vault inventories use their original password file. For a new one,
create a private one-line password file and protect it with chmod 600. Back up the
password separately; lost Vault passwords cannot be recovered.

```sh
export ANSIBLE_VAULT_PASSWORD_FILE=/private/path/vault-password
./clamav-mirror vault encrypt_string --prompt --name mirror_proxy_password
```

Place the encrypted value in inventory and reference it from mirror_proxy.password.
Without the environment variable, Ansible requests the password for inline !vault.
Working inventory, inventory-path, .hooks, .generated, and .secrets stay out of Git.

## Database updates and DNS

A dedicated clamav-mirror account runs cvdupdate with its state in mirror_home/.cvdupdate.
Systemd serializes timer runs; a file lock also excludes concurrent manual updater runs.
Logs go to journald; proxy URLs/passwords are redacted from captured cvdupdate output.
The first apply runs an update synchronously, then enables the timer. No cron is installed.
Existing base/state files can avoid upstream downloads, but import is not production-role logic.

DNS-disabled configurations do not request IAM tokens or call cloud APIs. With DNS enabled,
the target must be a Yandex Cloud VM with an attached service account permitted to read/update
record sets in the zone (for example dns.editor scoped to the zone). After cvdupdate succeeds,
the updater reads dns.txt, validates its format, obtains a metadata IAM token, and replaces
only the configured TXT record. It waits for the operation to complete. A database failure
never publishes DNS; a DNS failure leaves downloaded files available and fails the update unit.
verify compares the cloud API's TXT data to local dns.txt; recursive DNS caches may still lag
by TTL. Disabling publication leaves the existing cloud record intact.

## Caddy and system roles

Caddy serves files on HTTP without redirect and on HTTPS with automatic Let's Encrypt
issuance/renewal. Public DNS A/AAAA must point to the target; TCP 80/443 must be reachable.
Keep Caddy's certificate storage persistent. The Caddyfile is validated before reload.
The standard file server supports Range; verify requests 32 bytes of daily.cvd using
both protocols directly (ignoring controller proxy environment) and requires HTTP 206. Directory browsing is enabled only on HTTPS.

Common roles install minimal runtime/security packages, time sync, SSH fail2ban, UFW,
unattended-upgrades, and journald limits. Docker, nginx, Certbot and login notifier are
not installed. UFW permits SSH/80/443; it does not remove existing unrelated rules.
SSH policy disables root/password login and gives the configured administrator sudo.

## Hooks

Executable .hooks/post-config-change runs after success, followed by executable files
in .hooks/post-config-change.d in filename order. With --verify, checks precede hooks.
The first failure stops later hooks and returns nonzero; applied changes are not rolled back.
Working directory is the repository root. Environment: CLAMAVMIRROR_ROOT,
CLAMAVMIRROR_EVENT (post-config-change), CLAMAVMIRROR_INVENTORY and
CLAMAVMIRROR_ANSIBLE_INVENTORY (absolute paths to the selected inventory).
Hooks receive the whole inventory even with --limit. No integration hook is installed by default.

## Operations

Back up inventory/Vault password, database state, and certificate storage before upgrades.
Use plan, then apply --limit HOST --verify, then confirm a real FreshClam client can update.
verify is a readiness check, not a full FreshClam integration test. On verification failure,
configuration remains applied; there is no automatic general rollback. Restore known-good
configuration/data as needed, reapply and verify; keep console access.

```sh
sudo systemctl status caddy clamav-mirror-update.timer
sudo journalctl -u clamav-mirror-update --since '1 hour ago'
sudo systemctl start clamav-mirror-update.service
curl -fsS -H 'Range: bytes=0-31' https://mirror.example.com/daily.cvd
```

For ACME failures check DNS and firewall; for updates check upstream/proxy access and the
service journal; for DNS failures check metadata access and IAM scope. Status running alone
is insufficient. Avoid publishing captured traffic, configuration or unredacted credentials.
Temporary migration playbooks must remain outside Git; only one project manages the mirror.

## Development

./clamav-mirror check tests proxy encoding, optional DNS, record payload/verification,
failed-update behavior, CLI verification ordering and hooks. Run syntax checks with both
inventory examples. These checks do not issue certificates or deploy a full test VM.
