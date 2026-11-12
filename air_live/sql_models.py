"""Optional server-side SQL classification with an explicit direct fallback.

Disabled unless AIR_SQL_CONFIG points to a private cluster credential file or
AIR_SQL_JSON contains the equivalent server-only configuration.
"""
from .sql_cost import estimate
import json
import os
from pathlib import Path
from datetime import timedelta

SQL_COMPLETION = 'SELECT default:ai_completion($payload) AS response;'


def parse_completion(rows):
    if len(rows) != 1:
        raise ValueError('Unexpected SQL result count')
    value = rows[0].get('response')
    if not isinstance(value, list) or len(value) != 1:
        raise ValueError('Unexpected SQL completion envelope')
    text = value[0].get('response') if isinstance(value[0], dict) else None
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Missing SQL model answer')
    if text.strip().startswith('```'):
        text = text.strip().split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(text)


class SQLFirstModel:
    def __init__(self, direct, execute, fallback=None):
        self.direct, self.execute = direct, execute
        self.fallback = fallback or direct

    def __call__(self, kind, system, user):
        if kind != 'classify':
            return self.direct(kind, system, user)
        try:
            rows = self.execute(SQL_COMPLETION, {'payload': {
                'system_prompt': system, 'user_prompt': user,
                'temperature': 0, 'max_tokens': 600}})
            value = parse_completion(rows)
            from .engine import validate_classification
            validate_classification(value)
            return value, {'tokens_in': 0, 'tokens_out': 0,
                'usage_available': False, 'cache': 'n/a',
                'sql_estimate': estimate(system,user,rows[0]['response'][0]['response']),
                'model': 'amazon.nova-micro-v1:0', 'inference_path': 'sql',
                'attempts': 1}
        except Exception as error:
            # Do not persist exception messages: drivers may echo credentials.
            value, usage = self.fallback(kind, system, user)
            return value, {**usage, 'inference_path': 'direct_fallback',
                'sql_error_type': type(error).__name__, 'attempts': 2}


def sql_enabled():
    if os.environ.get('AIR_SQL_ENABLED') == '0':
        return False
    if os.environ.get('VERCEL'):
        return os.environ.get('AIR_SQL_ENABLED') == '1' and bool(os.environ.get('AIR_SQL_JSON'))
    return bool(os.environ.get('AIR_SQL_JSON') or os.environ.get('AIR_SQL_CONFIG'))


def local_sql_model(direct, fallback=None):
    raw = os.environ.get('AIR_SQL_JSON')
    path = os.environ.get('AIR_SQL_CONFIG')
    if not sql_enabled():
        return direct
    # Connection creation remains inside execute so connection failures also
    # reach the direct fallback. No credential or network changes are made.
    cluster = None
    def execute(statement, params):
        nonlocal cluster
        from couchbase.cluster import Cluster
        from couchbase.auth import PasswordAuthenticator
        from couchbase.options import ClusterOptions, QueryOptions
        if cluster is None:
            cfg = json.loads(raw) if raw else json.loads(Path(path).read_text())
            candidate = Cluster(cfg['connection_string'], ClusterOptions(
                PasswordAuthenticator(cfg['username'], cfg['password'])))
            candidate.wait_until_ready(timedelta(seconds=10))
            cluster = candidate
        return list(cluster.query(statement, QueryOptions(
            named_parameters=params, timeout=timedelta(seconds=25))).rows())
    return SQLFirstModel(direct, execute, fallback)
