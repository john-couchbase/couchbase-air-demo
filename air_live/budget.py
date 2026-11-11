"""Shared daily request ceiling with atomic reservations, including failed calls."""
import time
from datetime import datetime,timezone
from .sessions import Conflict,Missing,Busy

class Capacity(Busy): pass
class DailyLimit(Busy): pass

class Budget:
    def __init__(self,store,limit=48,prefix="air-budget",concurrency=3): self.store,self.limit,self.prefix,self.concurrency=store,limit,prefix,concurrency
    def reserve(self):
        key=self.prefix+'::'+datetime.now(timezone.utc).strftime('%Y-%m-%d')
        try:self.store.insert(key,{'calls':0,'leases':[]})
        except Conflict:pass
        for _ in range(20):
            doc,cas=self.store.get(key);now=time.time()
            leases=[x for x in doc['leases'] if x>now]
            if doc['calls']>=self.limit:raise DailyLimit('Today’s demo call limit has been reached.')
            if len(leases)>=self.concurrency:raise Capacity('Waiting for model capacity')
            lease=now+120;doc['calls']+=1;doc['leases']=leases+[lease]
            try:self.store.replace(key,doc,cas);return key,lease
            except Conflict:continue
        raise Busy('Budget updating')
    def release(self,reservation):
        key,lease=reservation
        for _ in range(20):
            try:doc,cas=self.store.get(key)
            except Missing:return
            doc['leases']=[x for x in doc['leases'] if x!=lease]
            try:self.store.replace(key,doc,cas);return
            except Conflict:continue
