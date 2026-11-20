"""Single stable PR gate; skipped irrelevant jobs are expected.

Only inspect GitHub-generated needs JSON. Do not run code/services or
contact external providers.
"""
import json
import os
import sys

ROUTED = (
    "backend",
    "frontend",
    "compose-config",
    "auth-db-migration",
    "deploy01-production-config",
    "deploy02-backup-e2e",
)


def main():
    try:
        needs = json.loads(os.environ["FOLIOSENTRY_CI_NEEDS"])
        changes = needs["changes"]
        if changes["result"] != "success":
            raise ValueError("ROUTER_FAILED")
        outputs = changes["outputs"]
        for key in ROUTED:
            enabled = outputs[key]
            if enabled not in ("true", "false"):
                raise ValueError("INVALID_ROUTE")
            expected = "success" if enabled == "true" else "skipped"
            if needs[key]["result"] != expected:
                raise ValueError("JOB_NOT_IN_EXPECTED_STATE:" + key)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print("FOLIOSENTRY_CI_FINAL_GATE_FAIL")
        sys.exit(1)
    print("FOLIOSENTRY_CI_FINAL_GATE_PASS")


if __name__ == "__main__":
    main()
