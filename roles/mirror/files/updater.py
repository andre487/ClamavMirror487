#!/usr/bin/env python3
"""Update databases, then optionally publish the DNS advertisement using YC metadata IAM."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

METADATA = "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
DNS_API = "https://dns.api.cloud.yandex.net/dns/v1/zones/"

def api(url, headers=None, payload=None):
    request = urllib.request.Request(url, headers=headers or {}, data=None if payload is None else json.dumps(payload).encode())
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    # Cloud metadata and control-plane requests must not use the download proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=20) as response:
        return json.load(response)

def advertisement(config):
    value = (Path(config["webroot"]) / "dns.txt").read_text().strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*(?::[0-9]+)+", value):
        raise ValueError("Invalid ClamAV DNS advertisement")
    return value

def dns_headers():
    token = api(METADATA, {"Metadata-Flavor": "Google"})["access_token"]
    return {"Authorization": "Bearer " + token}

def dns_url(config):
    zone = config["dns"]["zone_id"]
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", zone):
        raise ValueError("Invalid DNS zone ID")
    return DNS_API + zone

def check_dns(config):
    if not config.get("dns", {}).get("enabled", False):
        return
    query = urllib.parse.urlencode({"name": config["dns"]["record_name"], "type": "TXT"})
    current = api(dns_url(config) + ":getRecordSet?" + query, dns_headers())
    if current["data"] != [json.dumps(advertisement(config))]:
        raise RuntimeError("DNS advertisement differs from local dns.txt")

def publish_dns(config):
    dns = config.get("dns", {})
    if not dns.get("enabled", False):
        return
    value = advertisement(config)
    record = {"name": dns["record_name"], "type": "TXT", "ttl": str(dns.get("ttl", 300)), "data": [json.dumps(value)]}
    headers = dns_headers()
    operation = api(dns_url(config) + ":upsertRecordSets", headers, {"replacements": [record]})
    for _ in range(30):
        if operation.get("done"):
            if operation.get("error"):
                raise RuntimeError("Yandex Cloud DNS operation failed")
            return
        time.sleep(2)
        operation = api("https://operation.api.cloud.yandex.net/operations/" + operation["id"], headers)
    raise TimeoutError("Yandex Cloud DNS operation timed out")

def proxy_environment(config):
    env = os.environ.copy()
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        env.pop(key, None)
    proxy = config.get("proxy", {})
    if not proxy.get("host"):
        return env, []
    user = urllib.parse.quote(proxy["login"], safe="")
    password = urllib.parse.quote(proxy["password"], safe="")
    url = f"https://{user}:{password}@{proxy['host']}"
    env.update(http_proxy=url, https_proxy=url)
    return env, [url, proxy["password"], password]

def update(config):
    env, secrets = proxy_environment(config)
    for cmd in (["cvdupdate", "config", "set", "--dbdir", config["webroot"]], ["cvdupdate", "update"]):
        result = subprocess.run(cmd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1500)
        output = result.stdout
        for value in secrets:
            if value:
                output = output.replace(value, "[redacted]")
        print(output, end="", flush=True)
        if result.returncode:
            raise RuntimeError("cvdupdate failed; DNS was not published")
    publish_dns(config)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--verify-dns", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.verify_dns:
        check_dns(config)
        print("DNS verification passed or DNS is disabled")
        return
    # A file lock also excludes manual invocations; systemd already serializes the unit.
    with (Path(config["home"]) / ".update.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        update(config)

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Do not include request headers, tokens, proxy URLs or credentials in errors.
        print(f"Mirror operation failed ({type(error).__name__}); see sanitized cvdupdate output", file=sys.stderr)
        raise SystemExit(1)
