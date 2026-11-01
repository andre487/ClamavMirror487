"""Ansible launcher; inventory is native Ansible YAML with inline Vault values."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from hooks import run_hooks
ROOT = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inventory", type=Path)
    p.add_argument("--limit")
    p.add_argument("--no-hooks", action="store_true")
    p.add_argument("--verify", action="store_true", help="Verify after apply, before running hooks")
    p.add_argument("--tags")
    p.add_argument("--skip-tags")
    p.add_argument("--start-at-task")
    p.add_argument("command", choices=["deps", "plan", "apply", "verify", "update", "inventory", "vault", "check"])
    p.add_argument("--output", type=Path)
    p.add_argument("--dns", action="store_true", help="Use DNS-enabled inventory example")
    a, extra = p.parse_known_args()
    if a.verify and a.command != "apply":
        p.error("--verify is only supported with apply")
    if a.command == "check":
        code = subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT)
        if code:
            return code
        return subprocess.call(["ansible-playbook", "-i", "localhost,", "-c", "local", "tests/render.yml"], cwd=ROOT)
    if a.command == "deps":
        return subprocess.call(["ansible-galaxy", "collection", "list"], cwd=ROOT)
    if a.command == "vault":
        return subprocess.call(["ansible-vault", *extra], cwd=ROOT)
    if a.command == "inventory":
        output = (a.output or Path(input("Private inventory path: "))).expanduser().resolve()
        example = ROOT / ("inventory.dns.example.yml" if a.dns else "inventory.example.yml")
        with output.open("x") as target:
            os.chmod(output, 0o600)
            target.write(example.read_text())
        (ROOT / "inventory-path").write_text(str(output) + "\n")
        print(f"Created {output}; edit placeholders before plan/apply")
        return 0
    pointer = ROOT / "inventory-path"
    inventory = (a.inventory or Path(pointer.read_text().strip() if pointer.exists() else "inventory.yml")).expanduser().resolve()
    if not inventory.is_file():
        sys.exit(f"Inventory missing: {inventory}")
    play = "site" if a.command in ("plan", "apply") else a.command
    cmd = ["ansible-playbook", "-i", str(inventory), f"playbooks/{play}.yml"]
    if "!vault" in inventory.read_text() and not os.environ.get("ANSIBLE_VAULT_PASSWORD_FILE"):
        cmd += ["--ask-vault-pass"]
    if a.limit:
        cmd += ["--limit", a.limit]
    if a.command == "plan":
        cmd += ["--check"]  # Do not emit a diff containing credentials.
    selection = []
    for option in ("tags", "skip_tags", "start_at_task"):
        if getattr(a, option) is not None:
            selection += ["--" + option.replace("_", "-"), getattr(a, option)]
    code = subprocess.call(cmd + extra + selection, cwd=ROOT)
    if code == 0 and a.command == "apply" and a.verify:
        verify_cmd = cmd.copy()
        verify_cmd[3] = "playbooks/verify.yml"
        # Verify the selected hosts in full, regardless of apply's task filters.
        code = subprocess.call(verify_cmd + extra, cwd=ROOT)
    if code == 0 and a.command == "apply" and not a.no_hooks:
        code = run_hooks(ROOT, "post-config-change", inventory, inventory)
    return code

if __name__ == "__main__":
    raise SystemExit(main())
