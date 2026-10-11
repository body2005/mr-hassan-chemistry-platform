"""Anonymous Registry v2 checks; never read Docker credentials or print tokens."""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ACCEPT = ", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))


def get(url: str, headers: dict | None = None):
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=30) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers), error.read()


def probe(registry: str, repository: str, ref: str) -> dict:
    url = f"https://{registry}/v2/{repository}/manifests/{ref}"
    status, headers, body = get(url, {"Accept": ACCEPT})
    result = {"registry": registry, "repository": repository, "ref": ref, "anonymous_status": status}
    challenge = next((value for key, value in headers.items() if key.lower() == "www-authenticate"), "")
    if status == 401 and challenge.lower().startswith("bearer "):
        values = dict(re.findall(r'(\w+)="([^"]+)"', challenge))
        query = {key: values[key] for key in ("service", "scope") if key in values}
        token_status, _, token_body = get(values["realm"] + "?" + urlencode(query))
        result["token_status"] = token_status
        if token_status == 200:
            token_json = json.loads(token_body)
            token = token_json.get("token") or token_json.get("access_token")
            status, headers, body = get(url, {"Accept": ACCEPT, "Authorization": f"Bearer {token}"})
            result["authorized_manifest_status"] = status
    if status == 200:
        result["digest"] = next((value for key, value in headers.items() if key.lower() == "docker-content-digest"), None)
    else:
        try:
            result["error_codes"] = [item.get("code") for item in json.loads(body).get("errors", [])]
        except (ValueError, AttributeError):
            result["error_codes"] = ["non-json-response"]
    return result


if __name__ == "__main__":
    probes = [
        ("quay.io", "minio/minio", "RELEASE.2025-09-07T16-13-09Z"),
        ("quay.io", "minio/minio", "sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e"),
        ("quay.io", "minio/minio", "RELEASE.2025-09-06T17-38-46Z"),
        ("quay.io", "minio/mc", "RELEASE.2025-08-13T08-35-41Z"),
        ("quay.io", "minio/mc", "sha256:a7fe349ef4bd8521fb8497f55c6042871b2ae640607cf99d9bede5e9bdf11727"),
        ("registry-1.docker.io", "minio/minio", "RELEASE.2025-09-07T16-13-09Z"),
        ("registry-1.docker.io", "minio/mc", "RELEASE.2025-08-13T08-35-41Z"),
    ]
    for args in probes:
        try:
            print(json.dumps(probe(*args)))
        except Exception as error:
            print(json.dumps({"registry": args[0], "repository": args[1], "ref": args[2], "error": type(error).__name__}))
