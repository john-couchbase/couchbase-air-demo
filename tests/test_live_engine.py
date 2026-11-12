import unittest
from test_live_sessions import Store
from air_live.sessions import Sessions
from air_live.engine import Engine

class Tools:
 def run(self,token,name,**args):
  if name=='context': return [{'id':'sample-001','name':'Alex','tier':'Gold','message':'Help me rebook','options':[{'id':'evening'}]}]
  if name=='partners': return [{'id':'evening'}]
  return []
class EngineTests(unittest.TestCase):
 def setUp(self):
  self.s=Sessions(Store()); self.t=self.s.create(); self.s.start(self.t)
 def test_invalid_model_output_never_saved_as_decision(self):
  e=Engine(self.s,Tools(),lambda *a:({'intent':'bogus'},{}))
  with self.assertRaises(ValueError): e.advance(self.t)
  self.assertEqual(self.s.read(self.t)['status'],'error')
  self.assertEqual(self.s.read(self.t)['results'],[])
 def test_classification_from_model_is_saved(self):
  result={'intent':'rebook','urgency':3,'needs':['none'],'sentiment':'calm','language':'en','summary':'Needs a new flight'}
  e=Engine(self.s,Tools(),lambda *a:(result,{'tokens_in':50,'tokens_out':20}))
  e.advance(self.t)
  self.assertEqual(self.s.read(self.t)['results'][0]['classification'],result)
 def test_reset_during_model_call_discards_result(self):
  def model(*a):
   self.s.reset(self.t)
   return {'intent':'rebook','urgency':3,'needs':['none'],'sentiment':'calm','language':'en','summary':'Help'},{}
  Engine(self.s,Tools(),model).advance(self.t)
  self.assertEqual(self.s.read(self.t)['results'],[])

 def test_low_priority_skips_recovery_model(self):
  self.s.mutate(self.t,lambda d:d.update(results=[{'kind':'classify','request_id':'sample-001','classification':{'urgency':1}}]))
  def unexpected(*args): raise AssertionError('Recovery model must not run')
  Engine(self.s,Tools(),unexpected).advance(self.t)
  self.assertTrue(self.s.read(self.t)['results'][-1]['skipped'])
  self.assertFalse(self.s.read(self.t)['results'][-1]['routing_matched'])

 def test_live_activity_tracks_model_and_skips_reasoning(self):
  observed=[]
  def model(*args):
   observed.append(self.s.read(self.t)['flow_active']['stage'])
   return {'intent':'status','urgency':1,'needs':['none'],'sentiment':'calm','language':'en','summary':'Status request'},{}
  e=Engine(self.s,Tools(),model)
  e.advance(self.t); e.advance(self.t)
  doc=self.s.read(self.t)
  self.assertEqual(observed,['classify'])
  self.assertIsNone(doc['flow_active'])
  self.assertIn('route',[x['stage'] for x in doc['flow_events']])
  self.assertIn('standard',[x['stage'] for x in doc['flow_events']])
  self.assertNotIn('reason',[x['stage'] for x in doc['flow_events']])

 def test_stale_activity_cannot_repopulate_reset_run(self):
  claim=self.s.claim(self.t)
  self.s.reset(self.t)
  self.assertFalse(self.s.activity(self.t,claim,'reason','sample-001'))
  self.assertNotIn('flow_active',self.s.read(self.t))

 def test_reasoning_lights_only_after_routing_match(self):
  self.s.mutate(self.t,lambda d:d.update(results=[{'kind':'classify','request_id':'sample-001','classification':{'urgency':4}}]))
  class Routed(Tools):
   def run(self,token,name,**args):
    if name=='funnel': return [{'request_id':'sample-001'}]
    return super().run(token,name,**args)
  def model(*args):
   self.assertEqual(self.s.read(self.t)['flow_active']['stage'],'reason')
   return {'recommended_option':'evening','backup_option':'','goodwill_miles':0,'why':'Fits the request','reply':'Evening flight available','actions':[],'vouchers':[]},{}
  Engine(self.s,Routed(),model).advance(self.t)
  self.assertTrue(self.s.read(self.t)['results'][-1]['routing_matched'])
  self.assertIsNone(self.s.read(self.t)['flow_active'])
