import unittest
from air_live.presentation import bill
class CostTrackingTest(unittest.TestCase):
    def test_sql_and_measured_fallback_are_separate(self):
        report=bill({'results':[
            {'kind':'classify','inference_path':'sql','usage_available':False,'tokens_in':0,'tokens_out':0},
            {'kind':'classify','inference_path':'direct_fallback','usage_available':True,'tokens_in':100,'tokens_out':10},
            {'kind':'agent','tokens_in':200,'tokens_out':20},
            {'kind':'agent','skipped':True}]})
        self.assertEqual(report['tracking'],{'attempts':4,'measured':2,'estimated':0,'unknown':2})
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
        self.assertEqual(bill({'results':[]})['tracking'],{'attempts':0,'measured':0,'estimated':0,'unknown':0})


class SQLCostEstimateTest(unittest.TestCase):
    def test_old_saved_run_can_be_estimated_without_changing_measured_usage(self):
        result={'kind':'classify','inference_path':'sql','usage_available':False,'request_id':'r','classification':{'intent':'rebook'}}
        report=bill({'requests':[{'id':'r','message':'Help'}],'results':[result]})
        row=report['rows'][0]
        self.assertGreater(row['estimated_sql_usd'],0)
        self.assertEqual(row['spend_usd'],0)
        self.assertEqual(row['measured_calls'],0)
        self.assertEqual(report['tracking']['estimated'],1)
        self.assertNotIn('sql_estimate',result)
    def test_estimate_math(self):
        from air_live.sql_cost import estimate
        e=estimate('abc','defg','abcd')
        self.assertEqual((e['input_tokens'],e['output_tokens']),(2,1))
        self.assertAlmostEqual(e['cost_usd'],(2*.035+.14)/1e6)
