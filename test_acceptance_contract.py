import unittest
from acceptance_contract import completion, pending, transition


class RepairContract(unittest.TestCase):
    def setUp(self):
        self.expected = {key: {'control', 'target'} for key in ('a', 'b', 'c')}
        self.controls = {key: {'control'} for key in self.expected}
        self.green = {key: {'control': 'ok', 'target': 'ok'} for key in self.expected}

    def red(self, *keys):
        return {key: dict(cases, target='FAIL' if key in keys else 'ok')
                for key, cases in self.green.items()}

    def check(self, before, after, goal, stage):
        return transition(before, after, self.expected, self.controls, goal, stage)

    def test_one_real_repair_then_exhaustion(self):
        self.assertEqual(self.check(self.red('c'), self.green, 'c', 'exhausted'), set())
        completion({'c'}, ['c'], set())

    def test_two_real_repairs(self):
        self.assertEqual(self.check(self.red('a', 'b'), self.red('b'), 'a', 'next'), {'b'})
        self.assertEqual(self.check(self.red('b'), self.green, 'b', 'exhausted'), set())
        completion({'a', 'b'}, ['a', 'b'], set())

    def test_already_green_is_not_repair(self):
        self.assertEqual(pending(self.green, self.expected, self.controls), set())
        completion(set(), [], set())
        with self.assertRaises(ValueError):
            self.check(self.green, self.green, 'a', 'exhausted')

    def test_wrong_successor(self):
        for before, after, stage in [(self.red('a', 'b'), self.red('b'), 'exhausted'),
                                     (self.red('a'), self.green, 'next')]:
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                self.check(before, after, 'a', stage)

    def test_unrelated_repair_or_regression(self):
        for before, after in [(self.red('a', 'b'), self.green), (self.red('a'), self.red('b'))]:
            with self.assertRaises(ValueError):
                self.check(before, after, 'a', 'next')

    def test_invalid_inventory(self):
        for bad in ({}, {'a': {'control': 'ok'}}, dict(self.green, a={'control': 'FAIL', 'target': 'ok'}),
                    dict(self.green, a={'control': 'ok', 'target': 'ERROR'}),
                    dict(self.green, a={'control': 'ok', 'target': 'ok', 'extra': 'ok'})):
            with self.assertRaises(ValueError):
                pending(bad, self.expected, self.controls)

    def test_incomplete_or_duplicate_evidence(self):
        for initial, repaired, final in [({'a', 'b'}, ['a'], set()), ({'a'}, ['a', 'a'], set()),
                                          ({'a'}, ['a'], {'a'}), (set(), ['a'], set())]:
            with self.assertRaises(ValueError):
                completion(initial, repaired, final)
