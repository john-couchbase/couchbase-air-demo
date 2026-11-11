"""Server-only connection to the dedicated Air run collection."""
import json
import os
from datetime import timedelta
from pathlib import Path
from functools import lru_cache
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from .sessions import Sessions
from .store import CouchbaseStore

@lru_cache(maxsize=1)
def runtime():
    # Hosted secrets come from encrypted environment settings. Local development
    # can explicitly point at a private file outside the checkout.
    if os.environ.get('AIR_RUNTIME_JSON'):
        cfg=json.loads(os.environ['AIR_RUNTIME_JSON'])
    elif os.environ.get('AIR_RUNTIME_CONFIG'):
        cfg=json.loads(Path(os.environ['AIR_RUNTIME_CONFIG']).read_text())
    else:
        cfg={key:os.environ['AIR_'+key.upper()] for key in
             ('connection_string','username','password','bucket','scope','collection')}
    if (cfg['bucket'],cfg['scope'],cfg['collection']) != ('vector-learning','air_demo','runs'):
        raise RuntimeError('Air runtime must use its dedicated collection')
    cluster=Cluster(cfg['connection_string'],ClusterOptions(
        PasswordAuthenticator(cfg['username'],cfg['password'])))
    cluster.wait_until_ready(timedelta(seconds=20))
    collection=cluster.bucket(cfg['bucket']).scope(cfg['scope']).collection(cfg['collection'])
    return cluster, Sessions(CouchbaseStore(collection))
