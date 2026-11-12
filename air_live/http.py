"""Vercel-compatible, request-driven API. Never starts legacy global workers."""
import os
import time
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse
from .connection import runtime
from .sessions import Unauthorized,Busy
from .queries import couchbase_queries,QUERIES
from .engine import Engine,PROMPTS
from .models import ModelService
from .sql_models import local_sql_model, sql_enabled, SQL_COMPLETION
from .budget import Budget,Capacity,DailyLimit
from . import presentation as view
from .commands import catalogue

app=FastAPI()
@app.middleware('http')
async def private_responses(request,call_next):
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.exception_handler(Unauthorized)
async def unauthorized(req,err):return JSONResponse({'error':'Session unavailable. Reload to start a new run.'},status_code=401)
@app.exception_handler(Busy)
async def busy(req,err):return JSONResponse({'error':str(err)},status_code=409)

def services():
    c,s=runtime()
    direct=ModelService()
    def fallback(kind,system,user):
        budget=Budget(s.store,int(os.environ.get('AIR_DAILY_CALL_LIMIT','96')))
        reservation=budget.reserve()
        try:return direct(kind,system,user)
        finally:budget.release(reservation)
    model=local_sql_model(direct, fallback=fallback)
    return s,Engine(s,couchbase_queries(c,s),model)
def token(request):
    auth=request.headers.get('authorization','')
    if not auth.startswith('Bearer '):raise Unauthorized()
    value=auth[7:];runtime()[1].read(value);return value

def guarded(request):
    # Reject browser writes originating on a different site. No CORS wildcard.
    origin=request.headers.get('origin')
    if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
        # Vercel terminates TLS before forwarding the request.
        from urllib.parse import urlparse
        if urlparse(origin).netloc != request.headers.get('host'): raise HTTPException(403,'Origin not allowed')

@app.get('/api/health')
def health():
    c,s=runtime()
    s.store.collection.exists('air-readiness')
    return {'database':'connected','memory':'disabled','ai_functions':'configured' if sql_enabled() else 'not_configured','execution':'sql_with_direct_fallback' if sql_enabled() else 'direct_model_service'}
@app.post('/api/session')
def session(request:Request):
    guarded(request);s,e=services()
    budget=Budget(s.store,200,'air-session-budget',20)
    reservation=budget.reserve()
    try:
        t=s.create();e.initialize(t);return {'token':t}
    finally:budget.release(reservation)
@app.post('/api/advance')
def advance(request:Request):
    guarded(request);t=token(request);s,e=services()
    d=s.read(t)
    if d['status']!='running' or d['paused']:return {'advanced':False}
    if d['claim']:
        if d['claim']['expires_at']<=time.time():
            s.fail(t,d['claim'],'Previous step was interrupted. Restart to continue.')
        return {'advanced':False}
    budget=Budget(s.store,int(os.environ.get('AIR_DAILY_CALL_LIMIT','96')))
    try:reservation=budget.reserve()
    except Capacity:return {'advanced':False,'waiting':True}
    except DailyLimit:raise HTTPException(429,'Today’s demo call limit has been reached.') from None
    try:return {'advanced':e.advance(t)}
    except Busy:raise
    except Exception:raise HTTPException(502,'This step failed. No scripted result was substituted.') from None
    finally:budget.release(reservation)
@app.post('/api/{action}')
def control(action:str,request:Request):
    guarded(request);t=token(request);s,e=services()
    if action=='storm':s.start(t)
    elif action=='reset':s.reset(t);e.initialize(t)
    elif action in ('pause','resume'):s.pause(t,action=='pause')
    else:raise HTTPException(404)
    return view.state(s.read(t))
@app.post('/api/resolutions/{rid}/approve')
def approve(rid:str,request:Request):
    guarded(request);t=token(request);s,_=services()
    def apply(d):
        if not any(r['kind']=='agent' and r['request_id']==rid for r in d['results']):raise HTTPException(409,'Decision is not ready')
        d['approvals']=list(set(d.get('approvals',[])+[rid]))
    s.mutate(t,apply);return view.resolution(s.read(t),rid)
@app.get('/api/resolutions/{rid}')
def resolution(rid:str,request:Request):
    t=token(request);d=runtime()[1].read(t)
    try:return view.resolution(d,rid)
    except StopIteration:raise HTTPException(404,'Decision not available') from None
@app.get('/api/{name}')
def read(name:str,request:Request):
    t=token(request);c,s=runtime();d=s.read(t)
    if name=='state':return view.state(d)
    if name=='resolutions':return view.resolutions(d)
    if name=='bill':
        usage=couchbase_queries(c,s).run(t,'usage')
        report=view.bill(d)
        for row in report['rows']:
            measured=next((u for u in usage if u['job']==row['job']),{})
            row.update(calls=measured.get('calls',0),tokens_in=measured.get('tokens_in',0),tokens_out=measured.get('tokens_out',0))
            rate=view.RATES[row['job']]
            row['spend_usd']=(row['tokens_in']*rate[0]+row['tokens_out']*rate[1])/1000000
        report['statement']=QUERIES['usage']
        return report
    if name=='commands':return catalogue()
    if name=='sqlpp':return {'classify':SQL_COMPLETION if sql_enabled() else 'Direct Model Service call; SQL AI Function is not configured.',**QUERIES,**PROMPTS}
    if name=='models':return {'catalog':[],'backend':view.BACKEND}
    if name=='feed':
        rows=[]
        if d['status']=='ready':return rows
        for req in d['requests']:
            cls=next((r['classification'] for r in d['results'] if r['kind']=='classify' and r['request_id']==req['id']),None)
            rows.append({'id':req['id'],'name':req['name'],'ts':d['created_at'],'kind':'surge','channel':'chat','language':'en','text':req['message'],'classification':cls,'escalated':bool(cls and cls['urgency']>=3),**{k:req[k] for k in ('tier','flight_no','dest_city')}})
        return rows
    if name=='timeline':
        rows=[];cumulative=0
        for i,r in enumerate(d['results']):
            amount=view.cost(r);cumulative+=amount
            rows.append({'t':max(0,r['ts']-d['created_at']),'baseline':0,'surge':4 if i==0 else 0,'classified':int(r['kind']=='classify'),'hits':int(r.get('cache')=='hit'),'classify_usd':amount if r['kind']=='classify' else 0,'agent_usd':amount if r['kind']=='agent' else 0,'agent_calls':int(r['kind']=='agent'),'serverless_cum':cumulative,'reserved_cum':0,'reserved_rate':0})
        return {'bucket_s':1,'storm_at_s':0 if d['status']!='ready' else None,'quiet_at_s':None,'rows':rows}
    raise HTTPException(404)
