#!/usr/bin/env bash
# READ ONLY: print only safe Traefik compatibility hints for an existing PickNext.
# No .env, credentials, tokens, Traefik files, or other app settings are read.
set -Eeuo pipefail
command -v docker >/dev/null || { echo "DOCKER_CLI_UNAVAILABLE"; exit 1; }
command -v python3 >/dev/null || { echo "PYTHON3_UNAVAILABLE"; exit 1; }
docker info >/dev/null 2>&1 || { echo "DOCKER_DAEMON_UNAVAILABLE"; exit 1; }
python3 - <<'PY'
import json
import re
import subprocess

safe = re.compile(r"^[a-zA-Z0-9_.-]{1,100}$")
ids = subprocess.run(
    ["docker", "ps", "--format", "{{.ID}}"],
    check=True, capture_output=True, text=True
).stdout.splitlines()
seen_picknext = False
seen_traefik = False
print("TRAEFIK_DISCOVERY_MODE=READ_ONLY_REDACTED")
for container_id in ids:
    out = subprocess.run(
        ["docker", "inspect", container_id],
        check=True, capture_output=True, text=True
    ).stdout
    obj = json.loads(out)[0]
    name = (obj.get("Name") or "").lstrip("/")
    image = (obj.get("Config", {}).get("Image") or "").lower()
    is_picknext = bool(re.search(r"pick.?next", name, re.I))
    is_traefik = ("traefik" in name.lower() or image.startswith("traefik:"))
    if not (is_picknext or is_traefik):
        continue
    labels = obj.get("Config", {}).get("Labels") or {}
    net_names = list((obj.get("NetworkSettings", {}).get("Networks") or {}).keys())
    if is_traefik:
        seen_traefik = True
        print("EXISTING_TRAEFIK_CONTAINER=FOUND")
        for n in sorted(net_names):
            if safe.fullmatch(n):
                print("TRAEFIK_NETWORK_CANDIDATE=" + n)
    if is_picknext:
        seen_picknext = True
        print("EXISTING_PICKNEXT_CONTAINER=FOUND")
        network = labels.get("traefik.docker.network")
        if isinstance(network, str) and safe.fullmatch(network):
            print("PICKNEXT_ROUTER_NETWORK=" + network)
        for n in sorted(net_names):
            if safe.fullmatch(n):
                print("PICKNEXT_NETWORK_CANDIDATE=" + n)
        routers = set()
        for k in labels:
            m = re.fullmatch(r"traefik\.http\.routers\.([A-Za-z0-9_.-]+)\.rule", k)
            if m:
                routers.add(m.group(1))
        for router in sorted(routers):
            rule = labels.get("traefik.http.routers." + router + ".rule", "")
            if "picknext" not in str(rule).lower() and "picknext" not in router.lower():
                continue
            for label_name, key in (
                ("PICKNEXT_ENTRYPOINT", "entrypoints"),
                ("PICKNEXT_TLS_RESOLVER", "tls.certresolver"),
            ):
                v = labels.get("traefik.http.routers." + router + "." + key)
                if isinstance(v, str) and safe.fullmatch(v):
                    print(label_name + "=" + v)
print("PICKNEXT_FOUND=" + ("YES" if seen_picknext else "NO"))
print("TRAEFIK_FOUND=" + ("YES" if seen_traefik else "NO"))
print("NO_SECRET_OR_ENV_VALUES_PRINTED=YES")
print("TRAEFIK_DISCOVERY_READONLY_COMPLETE")
PY
