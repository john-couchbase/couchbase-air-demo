"""
Every read endpoint answers 200 against the running API.

    .venv/bin/python -m pytest tests/test_endpoints.py

SQL++ has a long list of reserved words (cache, language and option have all
bitten this demo) and a bad statement only fails when its endpoint is called.
This calls all of them, so a typo fails here rather than on stage.

Needs the API up on :8010. It does not trigger a storm or reset anything.
"""

import httpx
import pytest

BASE = "http://127.0.0.1:8010"
READS = ["/api/health", "/api/state", "/api/timeline", "/api/feed", "/api/resolutions",
         "/api/bill", "/api/sqlpp", "/api/models"]


@pytest.mark.parametrize("path", READS)
def test_read(path):
    r = httpx.get(BASE + path, timeout=30)
    assert r.status_code == 200, r.text[:300]


def test_resolution_detail_when_any():
    rows = httpx.get(BASE + "/api/resolutions", timeout=30).json()
    if not rows:
        pytest.skip("no resolutions yet; trigger a storm first")
    r = httpx.get(f"{BASE}/api/resolutions/{rows[0]['id']}", timeout=30)
    assert r.status_code == 200
    assert r.json()["decision"]
