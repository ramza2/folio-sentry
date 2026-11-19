#!/usr/bin/env python3
"""Read-only MiniPC Traefik ACME configuration inspection.

Reads only selected metadata fields of the existing Traefik container. Never
executes inside containers, inspects unrelated services, reads .env/acme.json/
config files, or requests environment variables, host mount source paths,
credentials, or raw Docker configurations.
"""
from __future__ import annotations

import json
from pathlib import PurePosixPath
import subprocess
import sys


def get_flag(args: list[str], key: str) -> str | None:
    expected = "--" + key.casefold()
    for arg in args:
        if not isinstance(arg, str):
            continue
        lowered = arg.casefold()
        if lowered == expected:
            return "true"
        if lowered.startswith(expected + "="):
            return arg.partition("=")[2]
    return None


def flag_enabled(value: str | None) -> bool:
    return bool(value) and value.casefold() not in {"false", "0", "no", "off"}


def persisted(storage: str | None, mounts: list[dict]) -> str:
    if not storage or not storage.startswith("/"):
        return "UNCONFIRMED"
    target = PurePosixPath(storage)
    for mount in mounts:
        destination = mount.get("Destination")
        if not isinstance(destination, str) or not destination.startswith("/"):
            continue
        base = PurePosixPath(destination)
        if base == target or base in target.parents:
            if mount.get("Type") in {"bind", "volume"}:
                return "MOUNT_PRESENT_NOT_BACKUP_VERIFIED"
    return "NO_MOUNT_SEEN_REVIEW"


def interpret(info: dict) -> dict[str, str]:
    cfg = info.get("Config") or {}
    args = [*(cfg.get("Entrypoint") or []), *(cfg.get("Cmd") or []), *(info.get("Args") or [])]
    prefix = "certificatesresolvers.myresolver.acme."
    http_ep = get_flag(args, prefix + "httpchallenge.entrypoint")
    tls = get_flag(args, prefix + "tlschallenge")
    dns = get_flag(args, prefix + "dnschallenge.provider")
    storage = get_flag(args, prefix + "storage")
    ca = get_flag(args, prefix + "caserver")
    challenge = [
        name for name, value in (
            ("HTTP_01", http_ep),
            ("TLS_ALPN_01", tls if flag_enabled(tls) else None),
            ("DNS_01", dns),
        ) if value
    ]
    # A resolver may instead be declared in a mounted static TOML/YAML.
    challenge_label = ",".join(challenge) if challenge else "NOT_VISIBLE_IN_COMMAND_FLAGS"
    if ca is None:
        ca_type = "DEFAULT_PRODUCTION_IF_FLAGS_ACTIVE"
    elif "staging" in ca.casefold():
        ca_type = "STAGING"
    else:
        ca_type = "CUSTOM_OR_PRODUCTION"

    net_mode = str((info.get("HostConfig") or {}).get("NetworkMode") or "")
    ports = (info.get("NetworkSettings") or {}).get("Ports") or {}
    bindings = (info.get("HostConfig") or {}).get("PortBindings") or {}
    def port_state(port: int) -> str:
        if net_mode == "host":
            return "HOST_NETWORK_INSPECT_EXTERNAL_REACHABILITY"
        published = ports.get(str(port) + "/tcp") or bindings.get(str(port) + "/tcp")
        return "PUBLISHED_BY_DOCKER_NOT_EXTERNAL_VERIFIED" if published else "NOT_DOCKER_PUBLISHED"

    return {
        "TRAEFIK_ACME_CHALLENGE": challenge_label,
        "ACME_HTTP_ENTRYPOINT": http_ep if http_ep and http_ep.isidentifier() else "NOT_CONFIRMED",
        "ACME_CA_CATEGORY": ca_type,
        "ACME_STORAGE_MOUNT": persisted(storage, info.get("Mounts") or []),
        "DOCKER_HOST_PORT_80": port_state(80),
        "DOCKER_HOST_PORT_443": port_state(443),
    }


def self_test() -> None:
    sample = {
        "Config": {
            "Image": "traefik:v3.5",
            "Cmd": [
                "--entrypoints.web.address=:80",
                "--certificatesresolvers.myresolver.acme.httpchallenge.entrypoint=web",
                "--certificatesresolvers.myresolver.acme.storage=/certs/acme.json",
                "--certificatesresolvers.myresolver.acme.email=do-not-print@example.invalid",
            ],
        },
        "HostConfig": {"NetworkMode": "bridge", "PortBindings": {
            "80/tcp": [{"HostPort": "80"}], "443/tcp": [{"HostPort": "443"}],
        }},
        "NetworkSettings": {"Ports": {}},
        "Mounts": [{"Type": "volume", "Destination": "/certs", "Name": "sensitive-do-not-print"}],
    }
    result = interpret(sample)
    assert result["TRAEFIK_ACME_CHALLENGE"] == "HTTP_01"
    assert result["ACME_HTTP_ENTRYPOINT"] == "web"
    assert result["ACME_STORAGE_MOUNT"] == "MOUNT_PRESENT_NOT_BACKUP_VERIFIED"
    assert result["DOCKER_HOST_PORT_80"].startswith("PUBLISHED")
    assert result["DOCKER_HOST_PORT_443"].startswith("PUBLISHED")
    sample["Config"]["Cmd"] = [
        "--certificatesresolvers.myresolver.acme.tlschallenge=true",
        "--certificatesresolvers.myresolver.acme.caserver=https://acme-staging-v02.example/",
    ]
    assert interpret(sample)["TRAEFIK_ACME_CHALLENGE"] == "TLS_ALPN_01"
    assert interpret(sample)["ACME_CA_CATEGORY"] == "STAGING"
    sample["Config"]["Cmd"] = ["--configFile=/etc/traefik/traefik.yml"]
    assert interpret(sample)["TRAEFIK_ACME_CHALLENGE"] == "NOT_VISIBLE_IN_COMMAND_FLAGS"
    assert interpret(sample)["ACME_STORAGE_MOUNT"] == "UNCONFIRMED"
    print("FOLIOSENTRY_TRAEFIK_ACME_INSPECT_SELFTEST_PASS")


def docker_field(container_id: str, field: str) -> object:
    """Ask Docker for one field, never request the whole Env/config object."""
    out = subprocess.run(
        ["docker", "inspect", "--format", "{{json " + field + "}}", container_id],
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout
    return json.loads(out)


def inspect() -> int:
    print("TRAEFIK_ACME_INSPECT_MODE=READ_ONLY_SELECTED_DOCKER_FIELDS")
    try:
        # Find Traefik by name/image without inspecting unrelated containers.
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}}|{{.Image}}|{{.Names}}"],
            check=True, capture_output=True, text=True, timeout=10,
        )
        ids: list[str] = []
        for line in result.stdout.splitlines():
            parts = line.split("|", 2)
            if len(parts) != 3:
                continue
            cid, image, name = parts
            image_name = image.casefold().split("/")[-1]
            if "traefik" in name.casefold() or image_name.startswith("traefik:"):
                ids.append(cid)
        if len(ids) != 1:
            print("REVIEW_TRAEFIK_CONTAINER=" +
                  ("NOT_FOUND" if not ids else "MULTIPLE_CANDIDATES"))
            return 2

        cid = ids[0]
        cmd = docker_field(cid, ".Config.Cmd") or []
        entry = docker_field(cid, ".Config.Entrypoint") or []
        args = docker_field(cid, ".Args") or []
        ports = docker_field(cid, ".NetworkSettings.Ports") or {}
        bindings = docker_field(cid, ".HostConfig.PortBindings") or {}
        network_mode = docker_field(cid, ".HostConfig.NetworkMode") or ""
        # Mount destinations/types only: source host paths and secret values
        # are never requested from the Docker daemon.
        mounts_out = subprocess.run(
            ["docker", "inspect", "--format",
             '{{range .Mounts}}{{.Type}}|{{.Destination}}{{println}}{{end}}', cid],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout
        mounts = []
        for line in mounts_out.splitlines():
            kind, sep, dest = line.partition("|")
            if sep:
                mounts.append({"Type": kind, "Destination": dest})
        obj = {
            "Config": {"Cmd": cmd, "Entrypoint": entry},
            "Args": args,
            "NetworkSettings": {"Ports": ports},
            "HostConfig": {"PortBindings": bindings, "NetworkMode": network_mode},
            "Mounts": mounts,
        }
        summary = interpret(obj)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        print("REVIEW_TRAEFIK_DOCKER=UNAVAILABLE")
        return 2
    for key, value in summary.items():
        print(key + "=" + value)
    print("TRAEFIK_CONFIG_FILES_READ=NO")
    print("TRAEFIK_ENV_OR_SECRET_VALUES_REQUESTED=NO")
    print("TRAEFIK_CONTAINERS_MODIFIED=NO")
    print("ROUTER_OR_CERTIFICATE_CREATED=NO")
    print("NOTE=DOCKER_PORT_MAPPING_DOES_NOT_PROVE_IPTIME_FORWARDING_OR_ACME_REACHABILITY")
    print("FOLIOSENTRY_TRAEFIK_ACME_READONLY_INSPECTION_COMPLETE")
    return 0

if __name__ == "__main__":
    if sys.argv[1:] == ["--self-test"]:
        self_test()
    elif len(sys.argv) == 1:
        sys.exit(inspect())
    else:
        print("Usage: python3 scripts/inspect-traefik-acme.py [--self-test]")
        sys.exit(2)
