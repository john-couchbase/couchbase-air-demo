import unittest
from air_live.presentation import bill
class CostTrackingTest(unittest.TestCase):
    def test_sql_and_measured_fallback_are_separate(self):
        report=bill({'results':[
            {'kind':'classify','inference_path':'sql','usage_available':False,'tokens_in':0,'tokens_out':0},
            {'kind':'classify','inference_path':'direct_fallback','usage_available':True,'tokens_in':100,'tokens_out':10},
            {'kind':'agent','tokens_in':200,'tokens_out':20},
            {'kind':'agent','skipped':True}]})
        self.assertEqual(report['tracking'],{'attempts':4,'measured':2,'unknown':2})
        rows={r['job']:r for r in report['rows']}
        self.assertEqual(rows['classify_sql']['calls'],2)
        self.assertFalse(rows['classify_sql']['usage_available'])
        self.assertEqual(rows['classify_direct']['tokens_in'],100)
        self.assertGreater(rows['classify_direct']['spend_usd'],0)
    def test_missing_direct_usage_is_not_measured_zero(self):
        report=bill({'results':[{'kind':'agent','usage_available':False,'tokens_in':0,'tokens_out':0}]})
        self.assertEqual(report['tracking']['unknown'],1)
        self.assertFalse(report['rows'][0]['usage_available'])
    def test_empty_run(self):
        self.assertEqual(bill({'results':[]})['tracking'],{'attempts':0,'measured':0,'unknown':0})
