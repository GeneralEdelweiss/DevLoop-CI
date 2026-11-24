"""Host-reviewed, *test-only* three-repair benchmark for the generic Eco DAG.

Not an implementation of the any actual product goal. It exercises its
scheduler/edit/test/integration contracts on three distinct dependencies.
The fixture and full independent test suite are created by this host module;
neither may be provided by a model or changed by a candidate.
"""
import hashlib

SOURCE_PATH = "eco_dag_example.py"
TEST_MODULE = "test_eco_dag_product"
SOURCE = """def evaluate(mode, x):
    if mode == 'double':
        return x + 1
    if mode == 'square':
        return x + 2
    if mode == 'bias':
        return x - 4
    return x
"""
FROZEN = """import unittest
from eco_dag_example import evaluate

class ProductContract(unittest.TestCase):
    def test_double(self):
        self.assertEqual(evaluate('double', 3), 6)

    def test_square(self):
        self.assertEqual(evaluate('square', 4), 16)

    def test_bias(self):
        self.assertEqual(evaluate('bias', 5), 9)

    def test_passthrough(self):
        self.assertEqual(evaluate('other', 7), 7)
"""

MANIFEST = {
    "schema": 1,
    "goal_id": "ECO-DEMO",
    "approval": "host-reviewed",
    "model": "qwen2.5-coder:7b",
    "source_path": SOURCE_PATH,
    "function": "evaluate",
    "test_module": TEST_MODULE,
    "frozen_sha256": hashlib.sha256(FROZEN.encode("utf-8")).hexdigest(),
    "positive_controls": ["test_passthrough"],
    "steps": [
        {
            "id": "ECO-DEMO.1", "depends_on": [],
            "target_test": "test_double",
            "anchor": "x + 1",
            "task": "When mode is double, the result must be twice x. Change the incorrect return expression only.",
            "priority": 1,
        },
        {
            "id": "ECO-DEMO.2", "depends_on": ["ECO-DEMO.1"],
            "target_test": "test_square",
            "anchor": "x + 2",
            "task": "When mode is square, the result must be x squared. Change the incorrect return expression only.",
            "priority": 1,
        },
        {
            "id": "ECO-DEMO.3", "depends_on": ["ECO-DEMO.2"],
            "target_test": "test_bias",
            "anchor": "x - 4",
            "task": "When mode is bias, the result must be x plus four. Change the incorrect return expression only.",
            "priority": 1,
        },
    ],
    "budget": {
        "concurrent_model_calls": 1,
        "attempts_per_step": 2,
        "num_ctx": 4096,
        "num_predict": 900,
        "max_prompt_chars": 6500,
        "model_downloads": False,
    },
}
