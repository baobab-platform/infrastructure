#!/usr/bin/env python3
"""Promote exact reviewed GHCR staging manifests into the staging ECR account.

Promotion is a deployment mutation and therefore runs only after the protected
staging apply role has been assumed. This script never rebuilds an image and
never changes a selected digest. The caller is responsible for registry login.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

REGION = "af-south-1"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
SHA = re.compile(r"[0-9a-f]{40}")
RUNTIME_IMAGES = {
    "cp": "baobab-cp",
    "iam": "baobab-iam-federation-authority",
    "pulse": "baobab-pulse",
    "keycloak": "baobab-iam",
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def promotion_plan(release_path):
    release_path = pathlib.Path(release_path)
    release_doc = load(release_path)
    release = release_doc.get("workload_release", release_doc)
    coordination_path = pathlib.Path(str(release_path).removesuffix(".tfvars.json") + ".coordination.json")
    coordination = load(coordination_path)

    account = release["account_id"]
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ValueError("invalid staging account")
    if set(coordination) != {"release_tag", "components"}:
        raise ValueError("invalid coordination document")

    expected_registry = f"{account}.dkr.ecr.{REGION}.amazonaws.com/"
    result = []
    for component, ghcr_name in RUNTIME_IMAGES.items():
        selected = coordination["components"][component]
        service = release["services"][component]
        digest = selected["digest"]
        if not DIGEST.fullmatch(digest) or not SHA.fullmatch(selected["source_revision"]):
            raise ValueError("invalid selected component identity")
        if service["source_revision"] != selected["source_revision"]:
            raise ValueError("runtime source revision differs from coordinated component")
        target = service["image"]
        if not target.startswith(expected_registry) or "@" not in target:
            raise ValueError("promotion target must be same-account ECR digest")
        target_repo, target_digest = target.rsplit("@", 1)
        target_digest = target_digest if target_digest.startswith("sha256:") else "sha256:" + target_digest
        if target_digest != digest:
            raise ValueError("promotion target digest differs from coordinated component")
        repository = target_repo.removeprefix(expected_registry)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_./-]{0,255}", repository):
            raise ValueError("invalid ECR repository")
        result.append({
            "component": component,
            "source": f"ghcr.io/baobab-platform/{ghcr_name}@{digest}",
            "source_revision": selected["source_revision"],
            "release_tag": selected["tag"],
            "digest": digest,
            "target_repo": target_repo,
            "repository": repository,
            "promotion_tag": "promotion-" + digest.removeprefix("sha256:")[:20],
        })
    return account, result


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise ValueError("promotion command failed: " + args[0])
    return result.stdout


def aws_json(args):
    output = command(["aws", "--region", REGION, "--no-cli-pager", "--output", "json", *args])
    return json.loads(output)


def ecr_image(repository, image_id):
    response = aws_json(["ecr", "batch-get-image", "--repository-name", repository, "--image-ids", image_id])
    if response.get("failures") or len(response.get("images", [])) != 1:
        return None
    image = response["images"][0]
    manifest = json.loads(image["imageManifest"])
    if "manifests" in manifest:
        raise ValueError("promotion selected an image index instead of linux/amd64 manifest")
    return image


def promote(item):
    existing = ecr_image(item["repository"], "imageDigest=" + item["digest"])
    if existing is not None:
        if existing["imageId"]["imageDigest"] != item["digest"]:
            raise ValueError("existing ECR digest identity mismatch")
        return {**item, "status": "already-present"}

    command(["docker", "pull", "--platform", "linux/amd64", item["source"]])
    inspected = json.loads(command(["docker", "image", "inspect", item["source"], "--format", "{{json .RepoDigests}}"]))
    if item["source"] not in inspected:
        raise ValueError("pulled GHCR image does not expose the selected digest")

    target_tag = item["target_repo"] + ":" + item["promotion_tag"]
    command(["docker", "tag", item["source"], target_tag])
    command(["docker", "push", target_tag])

    promoted = ecr_image(item["repository"], "imageTag=" + item["promotion_tag"])
    if promoted is None or promoted["imageId"]["imageDigest"] != item["digest"]:
        raise ValueError("ECR promotion changed the selected digest")
    by_digest = ecr_image(item["repository"], "imageDigest=" + item["digest"])
    if by_digest is None or by_digest["imageId"]["imageDigest"] != item["digest"]:
        raise ValueError("promoted digest is not retrievable by immutable identity")
    return {**item, "status": "promoted"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    account, items = promotion_plan(args.release)
    evidence = {
        "schema": "baobab.staging-promotion.v1",
        "account_id": account,
        "region": REGION,
        "components": [promote(item) for item in items],
        "operational_acceptance": False,
    }
    with open(args.output, "x", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print("staging image promotion denied: " + str(exc), file=sys.stderr)
        sys.exit(1)
