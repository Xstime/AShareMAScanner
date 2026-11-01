"""Read-only real HTTPS/IP-SAN mirror smoke probe. Never posts to VPS."""
import hashlib
import json
import urllib.request
from urllib.parse import urlsplit

BASE = "https://23.95.88.6:8443/ashare"
def request(url, *, method="GET", headers=None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    return urllib.request.urlopen(req, timeout=30)

with request(BASE + "/health") as res:
    assert res.status == 200, "VPS /health is not healthy"
with request(BASE + "/latest.json") as res:
    assert res.status == 200
    item = json.loads(res.read(262144))
assert item["schema_version"] == 1
assert item["repository"] == "Xstime/AShareMAScanner"
assert item["tag_name"].startswith("v")
assert item["sync_request_id"]
asset = next(a for a in item["assets"] if a["name"].endswith(".pyw"))
name = asset["name"]
sha = asset["digest"].split(":", 1)[1]
url = f"{BASE}/files/{sha}/{name}"
assert url == asset["browser_download_url"]
with request(url, method="HEAD") as res:
    assert res.status == 200
    etag = res.headers.get("ETag")
with request(url, headers={"Range": "bytes=0-1023"}) as res:
    assert res.status == 206
    assert res.headers.get("Content-Range") == f"bytes 0-1023/{asset['size']}"
    head = res.read()
    assert len(head) == 1024
with request(url) as res:
    assert res.status == 200
    data = res.read(4194305)
assert len(data) == asset["size"]
assert hashlib.sha256(data).hexdigest() == sha
print(f"Mirror HTTPS health/HEAD/206/full-SHA PASS tag={item['tag_name']} bytes={len(data)}")
