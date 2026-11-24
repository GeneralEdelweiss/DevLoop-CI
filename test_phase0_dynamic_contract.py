import copy
import unittest
from phase0_dynamic_contract import qualify_regression, plan_regressions


class Catalog:
    goals = {'DEMO-01': {'scope': ['tools/example.py']}}

    def binding(self, revision):
        return {'dev_revision': revision, 'policy_revision': 'a' * 40, 'catalog_digest': 'b' * 64}

    def eligible_subtasks(self, *, proven_goal_ids, blocked_goal_ids):
        return tuple(set(self.goals) - set(proven_goal_ids) - set(blocked_goal_ids))


class Tests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.rev = 'c' * 40
        self.path = 'tools/example.py'
        self.red = 'test_p0_example.Tests.test_invalid_input'
        self.green = 'test_p0_example.Tests.test_valid_input'
        self.proposal = {'goal': 'DEMO-01', 'path': self.path, 'symbol': 'example_function', 'target': self.red}
        self.args = {'approved_symbols': {self.path: ('example_function',)},
                     'reviewed_tests': {self.red: {'path': self.path, 'symbol': 'example_function',
                                                   'sha256': 'd' * 64, 'controls': [self.green],
                                                   'goal_ids': ['DEMO-01']}},
                     'baseline': {'binding': self.catalog.binding(self.rev), 'path': self.path, 'symbol': 'example_function',
                                  'source_sha256': 'e' * 64,
                                  'test_sha256': 'd' * 64, 'outcomes': {self.red: 'FAIL', self.green: 'ok'}}}

    def qualify(self, proposal=None, **kwargs):
        return qualify_regression(self.catalog, self.rev, self.proposal if proposal is None else proposal,
                                  **{**self.args, **kwargs})

    def test_revision_bound_candidate_not_admission(self):
        result = self.qualify()
        self.assertFalse(result['admission_permitted'])
        self.assertEqual(result['dev_revision'], self.rev)
        self.assertEqual(result, self.qualify())
        baseline = copy.deepcopy(self.args['baseline'])
        baseline['source_sha256'] = 'f' * 64
        self.assertNotEqual(result['contract_sha256'], self.qualify(baseline=baseline)['contract_sha256'])

    def test_scope_and_policy(self):
        for proposal in ({**self.proposal, 'goal': 'other'}, {**self.proposal, 'symbol': 'other'},
                         {**self.proposal, 'path': 'other.py'}, {**self.proposal, 'command': 'python'}):
            with self.subTest(proposal=proposal), self.assertRaises(ValueError):
                self.qualify(proposal)
        for args in ({'blocked': ('DEMO-01',)}, {'proven': ('DEMO-01',)}, {'occupied': (self.path.upper(),)}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.qualify(**args)

    def test_baseline_integrity(self):
        for change in ({'binding': self.catalog.binding('f' * 40)}, {'test_sha256': 'f' * 64},
                       {'path': 'other.py'}, {'symbol': 'other'},
                       {'outcomes': {self.red: 'ok', self.green: 'ok'}},
                       {'outcomes': {self.red: 'FAIL', self.green: 'FAIL'}},
                       {'outcomes': {self.red: 'ERROR', self.green: 'ok'}},
                       {'outcomes': {self.red: 'FAIL'}},
                       {'outcomes': {self.red: 'FAIL', self.green: 'ok', 'extra': 'ok'}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.qualify(baseline={**self.args['baseline'], **change})

    def test_review_integrity(self):
        for change in ({'symbol': 'other'}, {'goal_ids': []}, {'goal_ids': ['other']}, {'controls': []}, {'controls': [self.green, self.green]},
                       {'controls': [self.red]}, {'controls': ['test_other.Tests.test_ok']}):
            review = {**self.args['reviewed_tests'][self.red], **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.qualify(reviewed_tests={self.red: review})
        with self.assertRaises(ValueError):
            self.qualify(reviewed_tests={})

    def test_dynamic_selection_without_fixed_job(self):
        args = {k: v for k, v in self.args.items() if k != 'baseline'}
        args['baselines'] = {self.red: self.args['baseline']}
        result = plan_regressions(self.catalog, self.rev, **args)
        self.assertEqual(result, {'candidates': [self.qualify()], 'rejected': []})
        args['baselines'] = {}
        self.assertEqual(plan_regressions(self.catalog, self.rev, **args),
                         {'candidates': [], 'rejected': [{'target': self.red, 'reason': 'baseline_missing'}]})
        args['baselines'] = {self.red: {**self.args['baseline'], 'outcomes': {self.red: 'ok', self.green: 'ok'}}}
        self.assertEqual(plan_regressions(self.catalog, self.rev, **args),
                         {'candidates': [], 'rejected': [{'target': self.red, 'reason': 'qualification_rejected'}]})
        self.assertEqual(plan_regressions(self.catalog, self.rev, **args, proven=('DEMO-01',)),
                         {'candidates': [], 'rejected': []})
