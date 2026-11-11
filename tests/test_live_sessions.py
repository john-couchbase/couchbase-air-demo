import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from air_live.sessions import Sessions, Conflict, Missing, Unauthorized, Busy

class Store:
    def __init__(self): self.docs={}; self.lock=threading.Lock()
    def insert(self,key,value):
        with self.lock:
            if key in self.docs: raise Conflict()
            self.docs[key]=(copy.deepcopy(value),1)
    def get(self,key):
        with self.lock:
            if key not in self.docs: raise Missing()
            return copy.deepcopy(self.docs[key])
    def replace(self,key,value,cas):
        with self.lock:
            if self.docs[key][1]!=cas: raise Conflict()
            self.docs[key]=(copy.deepcopy(value),cas+1)

class Isolation(unittest.TestCase):
    def setUp(self):
        self.now=1000
        self.store=Store(); self.sessions=Sessions(self.store,lambda:self.now)
    def test_ten_visitors(self):
        tokens=[self.sessions.create() for _ in range(10)]
        self.assertEqual(len(set(tokens)),10)
        for token in tokens: self.sessions.start(token)
        with ThreadPoolExecutor(max_workers=10) as pool:
            claims=list(pool.map(self.sessions.claim,tokens))
        for i,(token,claim) in enumerate(zip(tokens,claims)):
            self.sessions.complete(token,claim,{'visitor':i})
        before=[self.sessions.read(t) for t in tokens]
        self.sessions.reset(tokens[0]); self.sessions.pause(tokens[1],True)
        self.assertEqual([self.sessions.read(t) for t in tokens[2:]],before[2:])
        for i,token in enumerate(tokens[2:],2): self.assertEqual(self.sessions.read(token)['results'][0]['visitor'],i)
    def test_unissued_capability_rejected(self):
        import secrets
        for token in ['', 'a'*43, secrets.token_urlsafe(32)]:
            with self.assertRaises(Unauthorized): self.sessions.read(token)
    def test_only_one_overlapping_claim(self):
        token=self.sessions.create(); self.sessions.start(token)
        def claim(_):
            try: return self.sessions.claim(token)
            except Busy: return None
        with ThreadPoolExecutor(max_workers=10) as pool: claims=list(pool.map(claim,range(10)))
        self.assertEqual(sum(c is not None for c in claims),1)
    def test_reset_rejects_old_completion(self):
        token=self.sessions.create(); self.sessions.start(token); claim=self.sessions.claim(token)
        self.sessions.reset(token)
        self.assertFalse(self.sessions.complete(token,claim,{'stale':True}))
        self.assertEqual(self.sessions.read(token)['results'],[])
    def test_other_visitor_cannot_commit_claim(self):
        a,b=self.sessions.create(),self.sessions.create()
        self.sessions.start(a); self.sessions.start(b)
        claim=self.sessions.claim(a)
        self.assertFalse(self.sessions.complete(b,claim,{'wrong':True}))
        self.assertEqual(self.sessions.read(b)['results'],[])
    def test_expired_claim_does_not_retry_chargeable_work(self):
        t=self.sessions.create(); self.sessions.start(t); self.sessions.claim(t); self.now+=121
        with self.assertRaises(Busy): self.sessions.claim(t)
        self.assertEqual(self.sessions.read(t)['status'],'interrupted')
    def test_pause_blocks_next_work(self):
        t=self.sessions.create(); self.sessions.start(t); self.sessions.pause(t,True)
        with self.assertRaises(Busy): self.sessions.claim(t)
    def test_limit_survives_reset(self):
        t=self.sessions.create()
        for _ in range(12):
            self.sessions.start(t); c=self.sessions.claim(t); self.sessions.complete(t,c,{}); self.sessions.reset(t)
        self.sessions.start(t)
        with self.assertRaises(Busy): self.sessions.claim(t)
        self.assertEqual(self.sessions.read(t)['calls'],12)

if __name__=='__main__': unittest.main()
