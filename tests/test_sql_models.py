import json
import unittest
from unittest.mock import patch
from air_live.sql_models import sql_enabled, local_sql_model
from air_live.sql_models import SQLFirstModel, parse_completion

VALID={'language':'en','intent':'rebook','urgency':4,'sentiment':'frustrated','needs':['connection'],'summary':'Find another flight'}

class SQLModelsTest(unittest.TestCase):
    def test_sql_success_does_not_call_fallback(self):
        from air_live.engine import validate_classification
        validate_classification(VALID)
        def execute(sql, params):
            self.assertIn('$payload',sql)
            self.assertEqual(params['payload']['user_prompt'],'untrusted message')
            return [{'response':[{'response':json.dumps(VALID)}]}]
        def direct(*args): self.fail('Unexpected fallback')
        value,usage=SQLFirstModel(direct,execute)('classify','rules','untrusted message')
        self.assertEqual(value,VALID)
        self.assertFalse(usage['usage_available'])
        self.assertEqual(usage['inference_path'],'sql')

    def test_error_empty_and_invalid_results_fall_back(self):
        for result in ([], [{'response':[{'error':'failure'}]}], [{'response':[{'response':'{}'}]}]):
            calls=[]
            def direct(*args): calls.append(args);return VALID,{'tokens_in':5}
            _,usage=SQLFirstModel(direct,lambda *a:result)('classify','s','u')
            self.assertEqual(len(calls),1)
            self.assertEqual(usage['inference_path'],'direct_fallback')

    def test_connection_failure_is_redacted(self):
        def fail(*args): raise RuntimeError('secret credential')
        _,usage=SQLFirstModel(lambda *a:(VALID,{}),fail)('classify','s','u')
        self.assertNotIn('secret',str(usage))
        self.assertEqual(usage['attempts'],2)

    def test_hosted_runtime_cannot_enable_local_sql(self):
        with patch.dict('os.environ', {'VERCEL':'1','AIR_SQL_CONFIG':'private.json'}, clear=True):
            self.assertFalse(sql_enabled())
            direct=object()
            self.assertIs(local_sql_model(direct),direct)

    def test_hosted_requires_explicit_enable_and_private_json(self):
        with patch.dict('os.environ', {'VERCEL':'1','AIR_SQL_JSON':'{}'}, clear=True):
            self.assertFalse(sql_enabled())
            with patch.dict('os.environ', {'AIR_SQL_ENABLED':'1'}):
                self.assertTrue(sql_enabled())
            with patch.dict('os.environ', {'AIR_SQL_ENABLED':'0'}):
                self.assertFalse(sql_enabled())

    def test_recovery_remains_direct(self):
        def fail(*args): self.fail('SQL used for recovery')
        self.assertEqual(SQLFirstModel(lambda *a:('direct',{}),fail)('agent','s','u')[0],'direct')

if __name__=='__main__': unittest.main()
