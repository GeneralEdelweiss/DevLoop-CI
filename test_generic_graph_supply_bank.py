import json
import unittest
from generic_graph_supply_bank import bank

class GraphBankTests(unittest.TestCase):
    def test_independent_contract_cases(self):
        targets=set()
        count=0
        for module,name,contract,cases in bank():
            self.assertNotIn(name,targets)
            targets.add(name)
            self.assertTrue(contract)
            for case in cases:
                with self.subTest(target=name,case=case["label"]):
                    try:
                        actual={"value":json.loads(json.dumps(getattr(module,name)(*case["args"])))}
                    except ValueError:
                        actual={"error":"ValueError"}
                    self.assertEqual(actual,case["expected"])
                    count+=1
        self.assertEqual(len(targets),6)
        self.assertGreaterEqual(count,130)
if __name__=="__main__":unittest.main()
