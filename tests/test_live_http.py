import unittest,time
from unittest.mock import patch
from fastapi.testclient import TestClient
from air_live.http import app
from air_live.sessions import Sessions
from air_live.budget import Capacity
from test_live_sessions import Store
class HttpTests(unittest.TestCase):
 def setUp(self):
  self.s=Sessions(Store());self.t=self.s.create();self.s.start(self.t)
  self.h={'Authorization':'Bearer '+self.t};self.client=TestClient(app)
  self.patch=patch('air_live.http.runtime',return_value=(None,self.s));self.patch.start()
  self.services=patch('air_live.http.services',return_value=(self.s,None));self.services.start()
 def tearDown(self):self.patch.stop();self.services.stop()
 def test_expired_claim_marked_error(self):
  self.s.claim(self.t)
  self.s.mutate(self.t,lambda d:d['claim'].update(expires_at=time.time()-1))
  self.assertEqual(self.client.post('/api/advance',headers=self.h).status_code,200)
  self.assertEqual(self.s.read(self.t)['status'],'error')
 def test_temporary_capacity_is_retryable(self):
  with patch('air_live.http.Budget.reserve',side_effect=Capacity()):
   r=self.client.post('/api/advance',headers=self.h)
  self.assertEqual(r.status_code,200);self.assertTrue(r.json()['waiting'])
 def test_cross_origin_write_denied(self):
  r=self.client.post('/api/reset',headers={**self.h,'Origin':'https://other.example'})
  self.assertEqual(r.status_code,403)
