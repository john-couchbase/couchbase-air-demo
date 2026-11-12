"""Map persisted live evidence to the existing frontend contract."""
import time
import json
from .sql_cost import estimate
from .engine import PROMPTS
from .sql_models import sql_enabled
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
    'spend':spend,'tokens':tokens,'reserved':{'label':'Comparison disabled','per_hour':0,'so_far':0},'models':{**NAMES,'classify':'Nova Micro (SQL)' if sql_enabled() else NAMES['classify']},'model_names':{k:{'name':('Nova Micro / direct fallback' if k=='classify' and sql_enabled() else v),'short':('Nova Micro' if k=='classify' and sql_enabled() else v)} for k,v in NAMES.items()},'backend':{**BACKEND, 'ai_functions':'query_service' if sql_enabled() else 'disabled','classify_via':'sqlpp' if sql_enabled() else 'backend'},
    'sql_evidence':{'enabled':sql_enabled(),'completed':sum(r.get('inference_path')=='sql' for r in cls),'fallbacks':sum(r.get('inference_path')=='direct_fallback' for r in cls)},
    'usage_incomplete':any(r.get('usage_available') is False or r.get('inference_path')=='direct_fallback' for r in results),
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
    """Keep measured direct usage separate from unreported SQL attempts."""
    results=[dict(r) for r in d['results'] if not r.get('skipped')]
    for r in results:
        if r.get('inference_path')=='sql' and not r.get('sql_estimate'):
            request=next((q for q in d.get('requests',[]) if q['id']==r.get('request_id')),None)
            if request and r.get('classification'):
                r['sql_estimate']=estimate(PROMPTS['classify_prompt'],request['message'],json.dumps(r['classification'],ensure_ascii=False))
                r['sql_estimate']['reconstructed']=True
    groups={}
    for r in results:
        path=r.get('inference_path','direct')
        if path=='direct_fallback':
            groups.setdefault(('classify','sql'),[]).append({'usage_available':False})
        groups.setdefault((r['kind'],'sql' if path=='sql' else 'direct'),[]).append(r)
    rows=[]
    for (kind,path),items in groups.items():
        measured=[r for r in items if r.get('usage_available',True)]
        available=len(measured)==len(items)
        estimates=[r['sql_estimate'] for r in items if r.get('sql_estimate') and not r.get('usage_available',True)]
        rows.append({'job':kind+'_'+path,
            'label':'SQL classification' if path=='sql' else 'Direct classification' if kind=='classify' else 'Recovery',
            'model':'Nova Micro' if path=='sql' else NAMES[kind],
            'estimated_calls':len(estimates),'estimated_tokens_in':sum(e['input_tokens'] for e in estimates),'estimated_tokens_out':sum(e['output_tokens'] for e in estimates),'estimated_sql_usd':sum(e['cost_usd'] for e in estimates),
            'calls':len(items),'measured_calls':len(measured),'usage_available':available,
            'cache_hits':sum(r.get('cache')=='hit' for r in measured),
            'tokens_in':sum(r.get('tokens_in',0) for r in measured),
            'tokens_out':sum(r.get('tokens_out',0) for r in measured),
            'spend_usd':sum(cost(r) for r in measured),'avoided_usd':0,'estimated':True})
    return {'statement':'','rows':rows,
        'tracking':{'attempts':sum(r['calls'] for r in rows),
                    'measured':sum(r['measured_calls'] for r in rows),
                    'estimated':sum(r['estimated_calls'] for r in rows),
                    'unknown':sum(r['calls']-r['measured_calls'] for r in rows)}}
