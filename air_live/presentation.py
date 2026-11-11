"""Map persisted live evidence to the existing frontend contract."""
import time
from .engine import REQUESTS
RATES={'classify':(.33,2.75),'agent':(2,10)} # Existing demo estimates, not a billing quote.
NAMES={'classify':'Nova 2 Lite','agent':'Claude Sonnet 5'}
BACKEND={'models':'model_service','cache':'model_service','ai_functions':'disabled','classify_via':'backend','memory':'disabled','endpoint':'Capella Model Service','stand_ins':{}}
def cost(r):
    rate=RATES[r['kind']];return (r.get('tokens_in',0)*rate[0]+r.get('tokens_out',0)*rate[1])/1000000

def state(d):
    results=d['results']; cls=[r for r in results if r['kind']=='classify'];agents=[r for r in results if r['kind']=='agent']
    elapsed=max(0,time.time()-d['created_at']);started=d['status']!='ready';claim=d.get('claim');kind=('classify' if claim['step']%2==0 else 'agent') if claim else None
    tokens={k:{'in':sum(r.get('tokens_in',0) for r in results if r['kind']==k),'out':sum(r.get('tokens_out',0) for r in results if r['kind']==k),'calls':sum(r['kind']==k and not r.get('skipped') for r in results)} for k in NAMES}
    spend={k:sum(cost(r) for r in results if r['kind']==k) for k in NAMES};spend['total']=sum(spend.values())
    return {'phase':'normal' if not started else 'quiet' if d['status']=='complete' else 'recovering' if agents else 'storm','paused':'user' if d['paused'] else None,
    'elapsed_s':elapsed,'storm_at_s':0 if started else None,'quiet_at_s':elapsed if d['status']=='complete' else None,
    'funnel':{'inbound':4 if started else 0,'classified':len(cls),'surge':4 if started else 0,'escalated':len(agents)+int(kind=='agent'),'in_agent':int(kind=='agent'),'approved':len(d.get('approvals',[]))},
    'cache':{'hits':sum(r.get('cache')=='hit' for r in cls),'misses':sum(r.get('cache')=='miss' for r in cls),'entries':0,'avoided_usd':0},
    'spend':spend,'tokens':tokens,'reserved':{'label':'Comparison disabled','per_hour':0,'so_far':0},'models':NAMES,'model_names':{k:{'name':v,'short':v} for k,v in NAMES.items()},'backend':BACKEND,
    'live':{'window_s':10,'arrivals_per_s':0,'classify_per_s':0,'cache_per_s':0,'classify_in_flight':int(kind=='classify'),'classify_slots':1,'agent_in_flight':int(kind=='agent'),'agent_slots':1,'spend_per_min':0,'reserved_per_min':0},
    'run_status':d['status'],'generation':d['generation'],'error':d.get('error'),'cost_estimated':True}

def resolutions(d):
    if d['status']=='ready':return []
    rows=[]
    for req in d.get('requests',REQUESTS):
        cls=next((r for r in d['results'] if r['kind']=='classify' and r['request_id']==req['id']),None)
        agent=next((r for r in d['results'] if r['kind']=='agent' and r['request_id']==req['id']),None)
        classification=cls['classification'] if cls else {'summary':'Waiting for classification','urgency':0,'needs':[]}
        rows.append({**req,'status':'approved' if req['id'] in d.get('approvals',[]) else 'drafted' if agent else 'drafting','created':d['created_at'],**{k:classification[k] for k in ('summary','urgency','needs')},'chosen':agent['decision']['recommended_option'] if agent else ''})
    return rows

def resolution(d,rid):
    req=next(r for r in d['requests'] if r['id']==rid)
    result=next(r for r in d['results'] if r['kind']=='agent' and r['request_id']==rid)
    return {**req,**result,'id':rid,'status':'approved' if rid in d.get('approvals',[]) else 'drafted','prompt':'Policy 2026.1 and SQL++ context','agent_via':'model_service','memory_used':{'disruptions':[],'preferences':{},'notes':[],'source':'disabled'}}

def bill(d):
    rows=[]
    for k in NAMES:
        results=[r for r in d['results'] if r['kind']==k and not r.get('skipped')]
        rows.append({'job':k,'model':NAMES[k],'calls':len(results),'cache_hits':sum(r.get('cache')=='hit' for r in results),'tokens_in':sum(r.get('tokens_in',0) for r in results),'tokens_out':sum(r.get('tokens_out',0) for r in results),'spend_usd':sum(cost(r) for r in results),'avoided_usd':0,'estimated':True})
    return {'statement':'','rows':rows}
