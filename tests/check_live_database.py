"""Explicit opt-in integration check; uses only disposable owned run records."""
from air_live.connection import runtime
from air_live.queries import couchbase_queries

def main():
    c,s=runtime(); q=couchbase_queries(c,s); tokens=[]
    try:
        tokens=[s.create(),s.create()]
        for token,city in zip(tokens,['New York','Seattle']):
            s.mutate(token,lambda d:d.update(requests=[{'id':'request-1','city':city,'options':[{'id':city}]}],results=[{'kind':'classify','request_id':'request-1','classification':{'urgency':4},'tokens_in':10,'tokens_out':4}]))
        assert q.run(tokens[0],'context',request_id='request-1')[0]['city']=='New York'
        assert q.run(tokens[1],'context',request_id='request-1')[0]['city']=='Seattle'
        assert q.run(tokens[0],'partners',request_id='request-1')==[{'id':'New York'}]
        assert len(q.run(tokens[0],'funnel'))==1
        assert q.run(tokens[0],'usage')[0]['tokens_in']==10
        print('PASS: four SQL++ tools; identical request IDs remain isolated.')
    finally:
        for token in tokens: s.store.collection.remove(s.key(token))
        c.close()

if __name__=='__main__': main()
