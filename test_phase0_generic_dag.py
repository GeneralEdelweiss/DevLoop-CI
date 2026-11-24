"""A generic DAG must fail closed before model calls, git writes or tests."""
import copy
import unittest

import phase0_generic_dag as dag
from phase0_generic_dag_fixture import MANIFEST, FROZEN

TESTS = {
    "test_double": "FAIL", "test_square": "FAIL",
    "test_bias": "FAIL", "test_passthrough": "ok",
}


def outcomes(values):
    return {f"{key} (test_eco_dag_product.ProductContract.{key})": value
            for key, value in values.items()}


def statuses():
    return {s["id"]: "pending" for s in MANIFEST["steps"]}


class GenericDagContracts(unittest.TestCase):
    def setUp(self):
        dag.validate(MANIFEST, FROZEN)

    def test_three_dependent_steps_require_independent_qualification(self):
        state = statuses()
        observed = outcomes(TESTS)
        first = dag.next_ready(MANIFEST, state, observed)
        self.assertEqual(first["id"], "ECO-DEMO.1")
        after1 = outcomes({**TESTS, "test_double": "ok"})
        self.assertEqual(dag.assess(MANIFEST, first, observed, after1, state),
                         "strict_partial_improvement")
        state[first["id"]] = "verified"
        second = dag.next_ready(MANIFEST, state, after1)
        self.assertEqual(second["id"], "ECO-DEMO.2")
        after2 = outcomes({**TESTS, "test_double": "ok", "test_square": "ok"})
        self.assertEqual(dag.assess(MANIFEST, second, after1, after2, state),
                         "strict_partial_improvement")
        state[second["id"]] = "verified"
        third = dag.next_ready(MANIFEST, state, after2)
        self.assertEqual(third["id"], "ECO-DEMO.3")
        after3 = outcomes({k: "ok" for k in TESTS})
        self.assertEqual(dag.assess(MANIFEST, third, after2, after3, state),
                         "all_frozen_tests_green")
        state[third["id"]] = "verified"
        self.assertIsNone(dag.next_ready(MANIFEST, state, after3))

    def test_priorities_respect_dependencies(self):
        plan = copy.deepcopy(MANIFEST)
        plan["steps"][2]["depends_on"] = []
        plan["steps"][2]["priority"] = 0
        first = dag.next_ready(plan, statuses(), outcomes(TESTS))
        self.assertEqual(first["id"], "ECO-DEMO.3")

    def test_cycle_self_missing_parent_rejected(self):
        for deps in (["ECO-DEMO.3"], ["ECO-DEMO.2"], ["ECO-DEMO.99"]):
            plan = copy.deepcopy(MANIFEST)
            plan["steps"][0]["depends_on"] = deps
            with self.subTest(deps=deps), self.assertRaises(ValueError):
                dag.validate(plan, FROZEN)

    def test_duplicate_step_id_target_or_orphan_suite_rejected(self):
        cases = []
        a = copy.deepcopy(MANIFEST)
        a["steps"][1]["id"] = a["steps"][0]["id"]
        cases.append(a)
        b = copy.deepcopy(MANIFEST)
        b["steps"][1]["target_test"] = b["steps"][0]["target_test"]
        cases.append(b)
        c = copy.deepcopy(MANIFEST)
        c["steps"].pop()
        cases.append(c)
        for item in cases:
            with self.assertRaises(ValueError):
                dag.validate(item, FROZEN)

    def test_unapproved_manifest_stale_test_bad_scope_rejected(self):
        for key, value in (("approval", "model-approved"), ("source_path", "../evil.py"),
                           ("source_path", "tools/../evil.py"),
                           ("function", "foo.bar.baz"), ("model", "remote-paid:model"),
                           ("frozen_sha256", "0" * 64)):
            manifest = copy.deepcopy(MANIFEST)
            manifest[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                dag.validate(manifest, FROZEN)
        with self.assertRaises(ValueError):
            dag.validate(MANIFEST, FROZEN.replace("16)", "17)"))

    def test_budget_overuse_and_download_rejected(self):
        for key, value in (("attempts_per_step", 4), ("concurrent_model_calls", 2),
                           ("num_ctx", 9000), ("num_predict", 901),
                           ("model_downloads", True), ("max_prompt_chars", 6501)):
            plan = copy.deepcopy(MANIFEST)
            plan["budget"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                dag.validate(plan, FROZEN)

    def test_outcome_inventory_duplicate_and_missing_rejected(self):
        full = outcomes(TESTS)
        invalid = [
            {k:v for k,v in full.items() if not k.startswith("test_double")},
            {**full, "test_extra (foo.ProductContract.test_extra)": "ok"},
            {**full, "test_bad (foo.ProductContract.test_bad)": "FAIL"},
            {**full, next(iter(full)): "ERROR"},
        ]
        for value in invalid:
            with self.assertRaises(ValueError):
                dag.normalize(MANIFEST, value)

    def test_regression_and_no_target_progress_fail(self):
        state = statuses()
        step = MANIFEST["steps"][0]
        a = outcomes(TESTS)
        self.assertEqual(dag.assess(MANIFEST, step, a, a, state),
                         "rejected_no_progress")
        after = outcomes({**TESTS, "test_double": "ok", "test_passthrough": "FAIL"})
        self.assertEqual(dag.assess(MANIFEST, step, a, after, state),
                         "rejected_regression")
        with self.assertRaises(ValueError):
            dag.next_ready(MANIFEST, state, after)

    def test_verified_step_regression_or_unapproved_early_pass_rejected(self):
        state = statuses()
        state["ECO-DEMO.1"] = "verified"
        with self.assertRaises(ValueError):
            dag.next_ready(MANIFEST, state, outcomes(TESTS))
        state = statuses()
        early = outcomes({**TESTS, "test_double": "ok"})
        with self.assertRaises(ValueError):
            dag.next_ready(MANIFEST, state, early)


if __name__ == "__main__":
    unittest.main()
