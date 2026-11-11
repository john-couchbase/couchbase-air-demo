import unittest
from air_live.queries import QUERIES, RunQueries
from air_live.sessions import Unauthorized

class Auth:
    def __init__(self): self.seen=[]
    def read(self,t):
        if t!='valid': raise Unauthorized()
        self.seen.append(t); return {'generation':'g'}
    def key(self,t): return 'owned-key'

class QueryTests(unittest.TestCase):
    def test_every_query_scopes_by_owned_key_and_generation(self):
        for sql in QUERIES.values():
            self.assertIn('USE KEYS $run_key',sql)
            self.assertIn('r.generation = $generation',sql)
            self.assertNotIn('travel-sample',sql)
    def test_unissued_session_cannot_execute_query(self):
        calls=[]; q=RunQueries(Auth(),lambda *a,**k:calls.append(a))
        with self.assertRaises(Unauthorized): q.run('bad','context',request_id='sample-001')
        self.assertEqual(calls,[])
    def test_named_parameters_no_interpolation(self):
        calls=[]
        def execute(sql,params): calls.append((sql,params)); return []
        q=RunQueries(Auth(),execute); q.run('valid','context',request_id='" OR TRUE')
        self.assertEqual(calls[0][1],{'run_key':'owned-key','generation':'g','request_id':'" OR TRUE'})
        self.assertNotIn('" OR TRUE',calls[0][0])

if __name__=='__main__': unittest.main()
