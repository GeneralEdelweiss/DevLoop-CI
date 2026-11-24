import copy
import unittest

from phase0_dynamic_contract import qualify_regression
from phase0_dynamic_dag import compile_dag, ready_step


class Catalog:
    goals = {'DEMO-01': {'scope': ['tools/example.py'], 'priority': 1}}

    def binding(self, revision):
        return {'dev_revision': revision, 'policy_revision': 'a' * 40,
                'catalog_digest': 'b' * 64}

    def eligible_subtasks(self, *, proven_goal_ids=(), blocked_goal_ids=()):
        return tuple(set(self.goals) - set(proven_goal_ids) - set(blocked_goal_ids))


class Tests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.rev = 'c' * 40
        self.goal = 'DEMO-01'
        self.path = 'tools/example.py'
        self.rows = []
        self.observed = {}
        for index in range(3):
            symbol = f'feature_{index}'
            target = f'test_p0_example.Tests.test_red_{index}'
            control = f'test_p0_example.Tests.test_green_{index}'
            test_sha = str(index + 1) * 64
            result = qualify_regression(
                self.catalog, self.rev,
                {'goal': self.goal, 'path': self.path, 'symbol': symbol, 'target': target},
                approved_symbols={self.path: (symbol,)},
                reviewed_tests={target: {'path': self.path, 'symbol': symbol,
                                        'sha256': test_sha, 'controls': [control],
                                        'goal_ids': [self.goal]}},
                baseline={'binding': self.catalog.binding(self.rev), 'path': self.path,
                          'symbol': symbol, 'source_sha256': 'd' * 64,
                          'test_sha256': test_sha, 'outcomes': {target: 'FAIL', control: 'ok'}})
            self.rows.append(result)
            self.observed[result['contract_sha256']] = {target: 'FAIL', control: 'ok'}
        self.keys = [row['contract_sha256'] for row in self.rows]
        self.edges = [(self.keys[1], self.keys[0]), (self.keys[2], self.keys[1])]

    def compile(self, rows=None, edges=None, revision=None):
        return compile_dag(self.catalog, revision or self.rev, self.goal,
                           self.rows if rows is None else rows,
                           self.edges if edges is None else edges)

    def ready(self, plan, verified, observations=None, revision=None):
        return ready_step(self.catalog, revision or self.rev, plan, self.rows, self.edges,
                          verified=verified, outcomes=self.observed if observations is None else observations)

    def test_three_dependencies_and_current_observations(self):
        plan = self.compile()
        self.assertFalse(plan['admission_permitted'])
        self.assertEqual(plan, self.compile(rows=list(reversed(self.rows))))
        self.assertEqual(len(plan['steps']), 3)
        verified = []
        for key in self.keys:
            step = self.ready(plan, verified)
            self.assertEqual(step['contract_sha256'], key)
            self.observed[key][step['target']] = 'ok'
            verified.append(step['id'])
        self.assertIsNone(self.ready(plan, verified))

    def test_rejects_cycles_and_duplicate_or_unbound_contracts(self):
        for edges in (self.edges + [(self.keys[0], self.keys[2])],
                      [(self.keys[0], 'f' * 64)], [(self.keys[0], self.keys[0])],
                      self.edges + [self.edges[0]]):
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                self.compile(edges=edges)
        for rows in (self.rows + [self.rows[0]], [{**self.rows[0], 'path': 'other.py'}, *self.rows[1:]],
                     [{**self.rows[0], 'target': 'changed'}, *self.rows[1:]]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.compile(rows=rows)

    def test_rejects_stale_plan_unverified_green_and_failed_control(self):
        plan = self.compile()
        with self.assertRaises(ValueError):
            self.ready(plan, [], revision='e' * 40)
        with self.assertRaises(ValueError):
            self.ready({**plan, 'admission_permitted': True}, [])
        step = self.ready(plan, [])
        key = step['contract_sha256']
        observed = copy.deepcopy(self.observed)
        observed[key][step['target']] = 'ok'
        with self.assertRaises(ValueError):
            self.ready(plan, [], observations=observed)
        observed = copy.deepcopy(self.observed)
        observed[key][self.rows[0]['controls'][0]] = 'FAIL'
        with self.assertRaises(ValueError):
            self.ready(plan, [], observations=observed)

    def test_rejects_completed_node_before_dependency(self):
        plan = self.compile()
        child = next(s for s in plan['steps'] if s['contract_sha256'] == self.keys[1])
        self.observed[self.keys[1]][child['target']] = 'ok'
        with self.assertRaises(ValueError):
            self.ready(plan, [child['id']])
