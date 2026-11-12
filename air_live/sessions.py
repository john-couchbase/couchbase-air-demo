"""Capability-owned run state and compare-and-swap work claims.

Only this module maps browser capabilities to keys. A caller never supplies a
collection, document key, or another visitor's ID. No process-global run state.
"""
from __future__ import annotations
import hashlib
import re
import secrets
import time

class Conflict(Exception): pass
class Missing(Exception): pass
class Unauthorized(Exception): pass
class Busy(Exception): pass

class Sessions:
    def __init__(self, store, clock=time.time):
        self.store, self.clock = store, clock

    @staticmethod
    def key(token):
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):
            raise Unauthorized('Session unavailable')
        return 'air-run::'+hashlib.sha256(token.encode()).hexdigest()

    def create(self):
        token=secrets.token_urlsafe(32)
        self.store.insert(self.key(token),self.fresh())
        return token

    def fresh(self, calls=0):
        return {'generation':secrets.token_hex(16),'created_at':self.clock(),
                'status':'ready','paused':False,'claim':None,'results':[],
                'calls':calls,'memory':'disabled'}

    def _get(self,token):
        try: return self.store.get(self.key(token))
        except Missing: raise Unauthorized('Session unavailable') from None

    def read(self,token):
        return self._get(token)[0]

    def mutate(self,token,fn):
        key=self.key(token)
        for _ in range(16):
            doc,cas=self._get(token)
            result=fn(doc)
            try: self.store.replace(key,doc,cas); return result
            except Conflict: continue
        raise Busy('Session is updating; try again')

    def start(self,token):
        def apply(d):
            if d['status']=='ready': d['status']='running'
        self.mutate(token,apply)

    def pause(self,token,paused):
        self.mutate(token,lambda d:d.update(paused=bool(paused)))

    def reset(self,token):
        def apply(d):
            fresh=self.fresh(d['calls']); d.clear(); d.update(fresh)
        self.mutate(token,apply)

    def claim(self,token):
        def apply(d):
            if d['claim']:
                if d['claim']['expires_at']<=self.clock(): d['status']='interrupted'
                return None
            if d['paused'] or d['status']!='running' or d['calls']>=12: return None
            c={'attempt':secrets.token_hex(16),'generation':d['generation'],
               'step':len(d['results']),'expires_at':self.clock()+120}
            d['claim']=c; d['calls']+=1
            return dict(c)
        claim=self.mutate(token,apply)
        if claim is None: raise Busy('No work available')
        return claim

    def activity(self,token,claim,stage,request_id):
        def apply(d):
            if d['claim']!=claim or d['generation']!=claim['generation']: return False
            d['flow_active']={'stage':stage,'request_id':request_id}
            events=d.setdefault('flow_events',[])
            events.append({'stage':stage,'request_id':request_id,'ts':self.clock()})
            d['flow_events']=events[-32:]
            return True
        return self.mutate(token,apply)

    def complete(self,token,claim,result):
        def apply(d):
            if d['claim']!=claim or d['generation']!=claim['generation']: return False
            if claim['expires_at']<=self.clock():
                d['status']='interrupted'; return False
            d['results'].append(result); d['claim']=None; d['flow_active']=None
            if len(d['results'])>=8: d['status']='complete'
            return True
        return self.mutate(token,apply)

    def fail(self,token,claim,code):
        def apply(d):
            if d['claim']!=claim: return False
            d['status']='error'; d['error']=code; d['claim']=None; d['flow_active']=None
            return True
        return self.mutate(token,apply)
