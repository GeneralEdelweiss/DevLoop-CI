import unittest
from generic_validation_supply import build_cases
class Tests(unittest.TestCase):
    def test_expansion_and_dedup(self):
        base={"count":1,"values":[1]}
        variants=[("zero",{"count":0},True),("negative",{"count":-1},False),
                  ("duplicate",{"count":-1},False),("both",{"count":2,"values":[1,2]},True)]
        rows=build_cases(base,variants)
        self.assertEqual(len(rows),4)
        self.assertEqual(rows[1]["expected"],{"value":{"count":0,"values":[1]}})
        self.assertEqual(rows[2]["expected"],{"error":"ValueError"})
        rows[0]["args"][0]["values"].append(3)
        self.assertEqual(base,{"count":1,"values":[1]})
        self.assertEqual(rows[0]["expected"]["value"]["values"],[1])
    def test_bounds_and_conflicting_oracles(self):
        base={"x":1}
        for rules in ([("bad",{"x":1},False)],[("unknown",{"y":0},False)],
                      [("bad",{"x":2},1)],[("same",{"x":2},True),("same",{"x":3},True)]):
            with self.assertRaises(ValueError):build_cases(base,rules)
        with self.assertRaises(ValueError):build_cases(base,[("extra",{"x":2},True)],limit=1)
    def test_type_sensitive_canonical(self):
        rows=build_cases({"x":1},[("boolean",{"x":True},False),("float",{"x":1.0},False)])
        self.assertEqual(len(rows),3)
if __name__=="__main__":unittest.main()
