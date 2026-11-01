"""Authenticated GitHub Actions-only Release notification for the deployed VPS.
No long-term keys, no disabled TLS checks, no client-side POST credentials.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = "Xstime/AShareMAScanner"
BASE = "https://23.95.88.6:8443/ashare"
AUD = BASE + "/publish"
GH = f"https://api.github.com/repos/{REPO}/releases/latest"


def fetch_json(url, headers=None, *, method="GET", data=None, timeout=20):
    req = urllib.request.Request(url, headers=headers or {
        "User-Agent": "AShareMAScanner-CI/1"}, data=data, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read(262145)
        if len(body) > 262144:
            raise RuntimeError("response too large")
        return response.status, json.loads(body)


def check_release(release):
    tag = release.get("tag_name")
    if (release.get("draft") is not False or release.get("prerelease") is not False
            or not isinstance(tag, str) or not re.fullmatch(r"v\d+\.\d+\.\d+", tag)):
        raise RuntimeError("GitHub latest is not a formal semver Release")
    names = {f"AShareMAScanner_{tag}.pyw", f"AShareMAScanner_{tag}.zip"}
    items = release.get("assets")
    if not isinstance(items, list) or len(items) != 2:
        raise RuntimeError("Release must contain the exact two expected assets")
    by_name = {x.get("name"): x for x in items if isinstance(x, dict)}
    if set(by_name) != names:
        raise RuntimeError("unexpected GitHub Release attachment")
    for name, x in by_name.items():
        if (not isinstance(x.get("size"), int) or isinstance(x.get("size"), bool)
                or not 0 < x["size"] <= 4194304
                or not re.fullmatch(r"sha256:[a-f0-9]{64}", str(x.get("digest", "")))
                or x.get("browser_download_url") !=
                f"https://github.com/{REPO}/releases/download/{tag}/{name}"):
            raise RuntimeError("invalid GitHub Release asset identity")
    return tag, by_name


def fresh_oidc_token():
    origin = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"]
    bearer = os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]
    if not origin.startswith("https://"):
        raise RuntimeError("GitHub OIDC URL is not HTTPS")
    sep = "&" if urllib.parse.urlsplit(origin).query else "?"
    endpoint = origin + sep + urllib.parse.urlencode({"audience": AUD})
    code, result = fetch_json(endpoint,
        {"Authorization": "bearer " + bearer}, timeout=15)
    token = result.get("value")
    if code != 200 or not isinstance(token, str) or token.count(".") != 2:
        raise RuntimeError("GitHub did not issue a valid OIDC JWT")
    return token


def synchronized(manifest, tag, request_id, assets):
    if manifest.get("tag_name") != tag or manifest.get("sync_request_id") != request_id:
        return False
    if (manifest.get("repository") != REPO or manifest.get("schema_version") != 1
            or manifest.get("draft") is not False or manifest.get("prerelease") is not False):
        raise RuntimeError("invalid mirror manifest identity")
    entries = manifest.get("assets")
    if not isinstance(entries, list) or len(entries) != len(assets):
        raise RuntimeError("mirror attachment count is wrong")
    for item in entries:
        name = item.get("name") if isinstance(item, dict) else None
        upstream = assets.get(name)
        if upstream is None:
            raise RuntimeError("unexpected mirror attachment")
        digest = upstream["digest"].split(":", 1)[1]
        if (item.get("size") != upstream["size"]
                or item.get("digest") != upstream["digest"]
                or item.get("upstream_download_url") != upstream["browser_download_url"]
                or item.get("browser_download_url") != f"{BASE}/files/{digest}/{name}"):
            raise RuntimeError("mirror release SHA / source / URL differs from GitHub")
    return True


def main():
    if (os.environ.get("GITHUB_REPOSITORY") != REPO
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or os.environ.get("GITHUB_EVENT_NAME") not in
            ("push", "workflow_dispatch", "workflow_run")):
        raise RuntimeError("not authorized GitHub main branch job")
    _, release = fetch_json(GH, {"User-Agent": "AShareMAScanner-CI/1",
        "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
        "Accept": "application/vnd.github+json"})
    tag, upstream = check_release(release)
    print("Verified latest GitHub Release: " + tag, flush=True)
    token = fresh_oidc_token()
    code, receipt = fetch_json(AUD, {"Authorization": "Bearer " + token,
        "Content-Type": "application/json", "User-Agent": "AShareMAScanner-CI/1"},
        method="POST", data=json.dumps({"tag": tag}).encode(), timeout=30)
    del token
    request_id = receipt.get("request_id")
    if code != 202 or not isinstance(request_id, str) or not request_id or len(request_id) > 256:
        raise RuntimeError("VPS did not accept the signed publication request")
    print("VPS accepted publication request_id=" + request_id, flush=True)
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        try:
            _, manifest = fetch_json(BASE + "/latest.json")
            if synchronized(manifest, tag, request_id, upstream):
                print(f"Mirror sync confirmed tag={tag} sync_request_id={request_id}",
                      flush=True)
                return
        except (TimeoutError, urllib.error.URLError, ValueError):
            pass
        time.sleep(5)
    raise RuntimeError("no mirror sync confirmation for exact request_id; FAILED")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"::error::VPS mirror synchronization failed: {type(exc).__name__}: {exc}",
              file=sys.stderr, flush=True)
        sys.exit(1)
