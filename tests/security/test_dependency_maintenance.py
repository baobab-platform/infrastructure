"""BA-SEC-DEP-001 infrastructure manifest/security source-policy tests.

The tests are offline checks, NOT live vulnerability scans, GitHub security
settings, Terraform plans/applies, provider credentials, or connected proof.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".github" / "dependabot.yml"
POLICY = ROOT / ".github" / "workflows" / "enforce-dependabot-config.yml"
SECURITY = ROOT / ".github" / "workflows" / "dependency-security.yml"
OWNERS = ROOT / ".github" / "CODEOWNERS"
GOVERNANCE = ROOT / "docs" / "security" / "dependency-maintenance.md"

EXPECTED = {
    ("github-actions", "/"),
    ("gomod", "/"),
    ("terraform", "/terraform/environments/staging"),
    ("npm", "/tests/platform-integration/devcontainer-cli"),
    ("npm", "/tests/platform-integration/int02/human"),
    ("docker", "/deploy/runtime-helper"),
    ("docker", "/.devcontainer/platform-integration"),
    ("docker", "/tests/platform-integration/int02/human"),
    ("docker-compose", "/compose"),
    ("docker-compose", "/tests/platform-integration"),
    ("docker-compose", "/tests/platform-integration/int02"),
    ("docker-compose", "/tests/platform-integration/int03"),
}

COMPOSE_NAMES = (
    "compose.yaml",
    "compose.yml",
    "docker-compose.yaml",
    "docker-compose.yml",
)


def violations(document: object) -> list[str]:
    """Review only declared/observable files; never invent security assurance."""
    errors: list[str] = []
    if not isinstance(document, dict) or document.get("version") != 2:
        return ["version"]
    updates = document.get("updates")
    if not isinstance(updates, list) or not updates:
        return ["updates"]
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(updates):
        if not isinstance(entry, dict):
            errors.append(f"invalid update {index}")
            continue
        ecosystem = entry.get("package-ecosystem")
        directory = entry.get("directory")
        if not isinstance(ecosystem, str) or not isinstance(directory, str):
            errors.append("missing ecosystem/directory")
            continue
        key = (ecosystem, directory)
        if key in seen:
            errors.append("duplicate manifest entry")
        seen.add(key)
        if not directory.startswith("/") or ".." in directory.split("/"):
            errors.append("unsafe directory")
            continue
        root = ROOT / directory.lstrip("/")
        if not root.is_dir():
            errors.append("missing directory")
            continue
        if "target-branch" in entry:
            errors.append("custom target branch")
        schedule = entry.get("schedule")
        if not isinstance(schedule, dict) or (
            schedule.get("interval") != "weekly"
            or schedule.get("timezone") != "Africa/Johannesburg"
            or schedule.get("day") != "monday"
            or not schedule.get("time")
        ):
            errors.append("schedule")
        limit = entry.get("open-pull-requests-limit")
        if type(limit) is not int or limit <= 0:
            errors.append("PR limit")
        if not isinstance(entry.get("labels"), list) or not entry["labels"]:
            errors.append("labels")
        message = entry.get("commit-message")
        if not isinstance(message, dict) or not message.get("prefix"):
            errors.append("commit prefix")
        for group in (entry.get("groups") or {}).values():
            if not isinstance(group, dict) or group.get("applies-to") != "version-updates":
                errors.append("unscoped groups")
            elif not (
                isinstance(group.get("patterns"), list)
                and group["patterns"]
                and isinstance(group.get("update-types"), list)
                and group["update-types"]
                and set(group["update-types"]).issubset({"minor", "patch"})
            ):
                errors.append("major/broad version group")
        for ignore in entry.get("ignore", []):
            if not isinstance(ignore, dict) or not ignore.get("update-types"):
                errors.append("unconditional ignore")
        # Valid config entries must correspond to manifest owners in THIS repo.
        if ecosystem == "github-actions" and not (ROOT / ".github/workflows").is_dir():
            errors.append("missing Actions")
        if ecosystem == "gomod" and not (root / "go.mod").is_file():
            errors.append("missing go.mod")
        if ecosystem == "terraform" and not (
            (root / "versions.tf").is_file() and
            (root / ".terraform.lock.hcl").is_file()
        ):
            errors.append("missing Terraform provider lock")
        if ecosystem == "npm" and not (
            (root / "package.json").is_file() and
            (root / "package-lock.json").is_file()
        ):
            errors.append("missing npm lock")
        if ecosystem == "docker" and not (root / "Dockerfile").is_file():
            errors.append("missing Dockerfile")
        if ecosystem == "docker-compose" and not any(
            (root / name).is_file() for name in COMPOSE_NAMES
        ):
            errors.append("missing Compose file")
    if not EXPECTED.issubset(seen):
        errors.append("missing required dependency surfaces")
    return errors


class InfrastructureDependencyMaintenancePolicyTests(unittest.TestCase):
    def setUp(self):
        self.source = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))

    def reject(self, message: str, mutate):
        candidate = deepcopy(self.source)
        mutate(candidate)
        self.assertIn(message, violations(candidate))

    def test_all_twelve_real_dependency_manifests(self):
        self.assertEqual(12, len(self.source["updates"]))
        self.assertEqual([], violations(self.source))

    def test_missing_go_ecosystem_rejected(self):
        self.reject(
            "missing required dependency surfaces",
            lambda doc: doc.update({
                "updates": [u for u in doc["updates"] if u["package-ecosystem"] != "gomod"]
            }),
        )

    def test_missing_staging_terraform_rejected(self):
        self.reject(
            "missing required dependency surfaces",
            lambda doc: doc.update({
                "updates": [u for u in doc["updates"] if u["package-ecosystem"] != "terraform"]
            }),
        )

    def test_missing_either_npm_consumer_rejected(self):
        self.reject(
            "missing required dependency surfaces",
            lambda doc: doc.update({
                "updates": [
                    u for u in doc["updates"]
                    if not (u.get("package-ecosystem") == "npm" and u.get("directory") == "/tests/platform-integration/int02/human")
                ]
            }),
        )

    def test_missing_automation_compose_rejected(self):
        self.reject(
            "missing required dependency surfaces",
            lambda doc: doc.update({
                "updates": [
                    u for u in doc["updates"]
                    if u.get("directory") != "/tests/platform-integration/int03"
                ]
            }),
        )

    def test_duplicate_surface_rejected(self):
        self.reject(
            "duplicate manifest entry",
            lambda doc: doc["updates"].append(deepcopy(doc["updates"][0])),
        )

    def test_nonexistent_manifest_directory_rejected(self):
        self.reject(
            "missing directory",
            lambda doc: doc["updates"][0].update({"directory": "/not-a-real-manifest"}),
        )

    def test_nondefault_branch_option_rejected(self):
        self.reject(
            "custom target branch",
            lambda doc: doc["updates"][0].update({"target-branch": "main"}),
        )

    def test_unguarded_group_could_mix_security_updates_rejected(self):
        self.reject(
            "unscoped groups",
            lambda doc: doc["updates"][0].update({
                "groups": {"all": {"patterns": ["*"]}}
            }),
        )

    def test_major_auto_group_rejected(self):
        self.reject(
            "major/broad version group",
            lambda doc: doc["updates"][0].update({
                "groups": {"all": {
                    "applies-to": "version-updates", "patterns": ["*"],
                    "update-types": ["major", "minor", "patch"],
                }}
            }),
        )

    def test_unconditional_ignore_rejected(self):
        self.reject(
            "unconditional ignore",
            lambda doc: doc["updates"][0].update({
                "ignore": [{"dependency-name": "*"}]
            }),
        )

    def test_disabled_pr_limit_rejected(self):
        self.reject(
            "PR limit",
            lambda doc: doc["updates"][0].update({"open-pull-requests-limit": 0}),
        )

    def test_accepted_shared_validator_and_six_ecosystem_inputs(self):
        text = POLICY.read_text(encoding="utf-8")
        self.assertIn(
            "enforce-dependabot-config.yml@"
            "31de2bc3dcd56128c019c640dc7e12c10ae9ca69",
            text,
        )
        self.assertIn(
            'required-ecosystems: "github-actions,gomod,terraform,npm,docker,docker-compose"',
            text,
        )
        self.assertNotIn('policy-level: "strict"', text)

    def test_daily_go_vulnerability_scan_is_pinned_and_fails(self):
        text = SECURITY.read_text(encoding="utf-8")
        self.assertIn('cron: "17 3 * * *"', text)
        self.assertIn("go run golang.org/x/vuln/cmd/govulncheck@v1.1.4 ./...", text)
        self.assertIn("go-version-file: go.mod", text)

    def test_both_locked_npm_consumers_are_audited(self):
        text = SECURITY.read_text(encoding="utf-8")
        for path in (
            "tests/platform-integration/devcontainer-cli",
            "tests/platform-integration/int02/human",
        ):
            self.assertIn(path, text)
        self.assertIn("npm ci --ignore-scripts --no-audit --no-fund", text)
        self.assertIn("npm audit --audit-level=high", text)
        self.assertNotIn("npm audit --omit=dev", text)

    def test_terraform_lock_validation_does_not_grant_cloud_execution(self):
        text = SECURITY.read_text(encoding="utf-8")
        self.assertIn("terraform init -backend=false -lockfile=readonly", text)
        self.assertIn("terraform validate", text)
        self.assertNotRegex(text, r"\bterraform\s+(?:plan|apply|destroy)\b")
        self.assertNotIn("id-token: write", text)
        self.assertNotIn("STAGING_APPLY_ROLE_ARN", text)

    def test_protected_staging_apply_approval_is_unchanged(self):
        text = (ROOT / ".github/workflows/staging-deploy.yml").read_text()
        self.assertIn("environment: staging", text)
        self.assertIn("if: inputs.apply", text)

    def test_policy_owners_include_independent_security_review(self):
        text = OWNERS.read_text(encoding="utf-8")
        for path in (
            "/.github/",
            "/.github/dependabot.yml",
            "/docs/security/dependency-maintenance.md",
            "/terraform/environments/staging/",
        ):
            self.assertIn(path, text)
        self.assertIn("@baobab-platform/security", text)

    def test_evidence_states_and_uncovered_safety_gates_remain_distinct(self):
        text = GOVERNANCE.read_text(encoding="utf-8")
        for token in (
            "BA-SEC-DEP-001", "SOURCE_COMMITTED", "CI_VERIFIED",
            "SECURITY_ALERT_PATH_VERIFIED", "BLOCKED", "CONSUMER_QUALIFIED",
            "Terraform provider advisories", "dynamic Compose images",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
