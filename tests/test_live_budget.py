import unittest
from concurrent.futures import ThreadPoolExecutor
from test_live_sessions import Store
from air_live.budget import Budget
from air_live.sessions import Busy
class BudgetTests(unittest.TestCase):
 def test_shared_limit(self):
  b=Budget(Store(),4)
  for _ in range(4): r=b.reserve();b.release(r)
  with self.assertRaises(Busy):b.reserve()
 def test_concurrency(self):
  b=Budget(Store())
  def reserve(_):
   try:return b.reserve()
   except Busy:return None
  with ThreadPoolExecutor(max_workers=10) as p:r=list(p.map(reserve,range(10)))
  self.assertEqual(sum(x is not None for x in r),3)
