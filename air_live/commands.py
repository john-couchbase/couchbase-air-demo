"""One command catalogue for the server and optional technical inspector."""
from .sql_models import sql_enabled, SQL_COMPLETION
from .queries import QUERIES
from .engine import PROMPTS, AGENT_PROMPT

def catalogue():
    return {'mode':'reference','sections':[
        {'id':'classify','title':'Classify the message','kind':'SQL++' if sql_enabled() else 'Model Service','note':'SQL classification with direct model fallback.' if sql_enabled() else 'Direct model call. SQL AI Function is not configured on this cluster.','code':SQL_COMPLETION if sql_enabled() else 'POST /v1/chat/completions\nmodel: CLASSIFY_MODEL_NAME\nmessages: system prompt + passenger message'},
        {'id':'context','title':'Look up the request','kind':'SQL++','note':'Reads only the visitor’s current run.','code':QUERIES['context']},
        {'id':'partners','title':'Find available options','kind':'SQL++','note':'Reads the options supplied for this scenario, not live airline inventory.','code':QUERIES['partners']},
        {'id':'funnel','title':'Route urgent requests','kind':'SQL++','note':'Selects classified requests with urgency of three or higher.','code':QUERIES['funnel']},
        {'id':'agent','title':'Draft a recovery decision','kind':'Model Service','note':'Receives the request, options and policy.','code':AGENT_PROMPT},
        {'id':'usage','title':'Read token usage','kind':'SQL++','note':'Totals recorded calls for this run.','code':QUERIES['usage']},
        {'id':'policy','title':'Recovery policy','kind':'2026.1','note':'The policy sent with the recovery request.','code':PROMPTS['policy']},
        {'id':'classify_prompt','title':'Classification prompt','kind':'Prompt','note':'The original classification rules.','code':PROMPTS['classify_prompt']},
        {'id':'save','title':'Save results safely','kind':'Couchbase SDK','note':'CAS rejects conflicting writes. Reset changes the generation so old work cannot overwrite a new run.','code':'collection.replace(run_key, document, ReplaceOptions(cas=version, preserve_expiry=True))'},
    ]}

if __name__=='__main__':
    import json
    print(json.dumps(catalogue(),indent=2))
