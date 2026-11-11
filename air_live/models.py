"""Direct Capella Model Service calls; no memory or local model fallback."""
import json
import os
from pathlib import Path
import httpx

class ModelService:
    def __init__(self,config=None):
        self.config=config or (json.loads(os.environ['AIR_MODEL_JSON']) if os.environ.get('AIR_MODEL_JSON') else None) or (json.loads(Path(os.environ['AIR_MODEL_CONFIG']).read_text()) if os.environ.get('AIR_MODEL_CONFIG') else {k:os.environ['AIR_'+k] for k in ('MODEL_BASE_URL','MODEL_API_KEY','CLASSIFY_MODEL_NAME','AGENT_MODEL_NAME','AGENT_API_KEY')})
    def __call__(self,kind,system,user):
        cfg=self.config; name=cfg['CLASSIFY_MODEL_NAME' if kind=='classify' else 'AGENT_MODEL_NAME']
        key=cfg['MODEL_API_KEY' if kind=='classify' else 'AGENT_API_KEY']
        response=httpx.post(cfg['MODEL_BASE_URL'].rstrip('/')+'/chat/completions',
            headers={'Authorization':'Bearer '+key},timeout=90,
            json={'model':name,'messages':[{'role':'system','content':system},{'role':'user','content':user}], 'max_tokens':600 if kind=='classify' else 1000})
        if response.status_code!=200: raise RuntimeError('Model Service returned HTTP '+str(response.status_code))
        body=response.json(); raw=body['choices'][0]['message']['content'].strip()
        if raw.startswith('```'): raw=raw.split('\n',1)[1].rsplit('```',1)[0]
        value=json.loads(raw); usage=body.get('usage',{})
        cache=response.headers.get('x-cache','').lower()
        return value,{'tokens_in':usage.get('prompt_tokens',0),'tokens_out':usage.get('completion_tokens',0),
                      'cache':'hit' if cache=='hit' else 'miss' if cache=='miss' else 'n/a','model':name}
