"""
One cluster connection for the whole process, and the keyspaces it uses.

Everything the demo produces lands in `aidp-air`.`ops`: the storm's inbound
messages, the classification the cheap model writes onto them, the frontier agent's
drafts, agent memory and the token meter. Keeping it in one scope is the
point - the whole run can be read back in SQL++.
"""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Any

from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions, QueryOptions
from couchbase.n1ql import QueryScanConsistency

from aidpair.config import settings

COLLECTIONS = [
    "flights", "passengers", "bookings", "messages",
    "resolutions", "memory", "meter",
]


@lru_cache
def cluster() -> Cluster:
    s = settings()
    auth = (PasswordAuthenticator(s.cb_user, s.cb_pass, cert_path=s.cb_cert_path)
            if s.cb_cert_path else PasswordAuthenticator(s.cb_user, s.cb_pass))
    opts = ClusterOptions(auth)
    if s.cb_conn.startswith("couchbases://"):
        # Capella over the internet: longer timeouts than a laptop cluster needs.
        opts.apply_profile("wan_development")
    c = Cluster(s.cb_conn, opts)
    c.wait_until_ready(timedelta(seconds=30))
    return c


def bucket():
    return cluster().bucket(settings().cb_bucket)


def coll(name: str):
    return bucket().scope(settings().cb_scope).collection(name)


def ks(name: str) -> str:
    """Fully qualified keyspace, for SQL++ text."""
    s = settings()
    return f"`{s.cb_bucket}`.`{s.cb_scope}`.`{name}`"


def query(statement: str, *, fresh: bool = False, **params: Any) -> list[dict]:
    kw: dict[str, Any] = {}
    if params:
        kw["named_parameters"] = params
    if fresh:
        kw["scan_consistency"] = QueryScanConsistency.REQUEST_PLUS
    return list(cluster().query(statement, QueryOptions(**kw)).rows())
