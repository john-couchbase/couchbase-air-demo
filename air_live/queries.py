"""Executable SQL++ shared by runtime tools and the command inspector.

Inputs and results live inside one capability-owned run. No shared flights,
passengers, memory, or original demo documents are read or mutated.
"""
KEYSPACE='`vector-learning`.`air_demo`.`runs`'
QUERIES={
 'context':f'''SELECT RAW request
FROM {KEYSPACE} AS r USE KEYS $run_key
UNNEST r.requests AS request
WHERE r.generation = $generation AND request.id = $request_id;''',
 'partners':f'''SELECT RAW opt
FROM {KEYSPACE} AS r USE KEYS $run_key
UNNEST r.requests AS request
UNNEST request.`options` AS opt
WHERE r.generation = $generation AND request.id = $request_id;''',
 'funnel':f'''SELECT result.request_id, result.classification
FROM {KEYSPACE} AS r USE KEYS $run_key
UNNEST r.results AS result
WHERE r.generation = $generation
AND result.kind = "classify"
AND result.classification.urgency >= 3;''',
 'usage':f'''SELECT result.kind AS job, SUM(result.tokens_in) AS tokens_in,
       SUM(result.tokens_out) AS tokens_out, COUNT(*) AS calls
FROM {KEYSPACE} AS r USE KEYS $run_key
UNNEST r.results AS result
WHERE r.generation = $generation AND IFMISSINGORNULL(result.skipped, FALSE) = FALSE
GROUP BY result.kind;''',
}

class RunQueries:
    def __init__(self,sessions,execute): self.sessions,self.execute=sessions,execute
    def run(self,token,name,**params):
        doc=self.sessions.read(token)
        if set(params)-{'request_id'}: raise ValueError('Unsupported query parameter')
        bound={**params,'run_key':self.sessions.key(token),'generation':doc['generation']}
        return self.execute(QUERIES[name],bound)

def couchbase_queries(cluster,sessions):
    from couchbase.options import QueryOptions
    def execute(sql,params):
        return list(cluster.query(sql,QueryOptions(named_parameters=params,read_only=True)).rows())
    return RunQueries(sessions,execute)
