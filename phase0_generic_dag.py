"""Generic, host-approved Eco microtask DAG (synthetic and host-reviewed plans).

No model code, tests or paths are trusted. The plan is host-authored and
independently pinned to a frozen product suite. This pure module never writes
files or invokes a model: the VM runner and Docker product gate do that.
"""
import ast
from collections.abc import Mapping
import hashlib
import json
import re

_BUDGET = {
    "concurrent_model_calls": 1,
    "attempts_per_step": 2,
    "num_ctx": 4096,
    "num_predict": 900,
    "max_prompt_chars": 6500,
    "model_downloads": False,
}
_STEP = re.compile(r"[A-Z][A-Z0-9-]{1,45}\.[0-9]{1,3}\Z")
_GOAL = re.compile(r"[A-Z][A-Z0-9-]{2,55}\Z")
_PATH = re.compile(r"[A-Za-z_][A-Za-z_0-9/.-]{0,180}\.py\Z")
_TEST = re.compile(r"test_[A-Za-z0-9_]{1,90}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_KEYS = {"schema", "goal_id", "approval", "model", "source_path", "function",
         "test_module", "frozen_sha256", "positive_controls", "steps", "budget"}
_STEP_KEYS = {"id", "depends_on", "target_test", "anchor", "task", "priority"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def test_names(frozen_text):
    if not isinstance(frozen_text, str) or len(frozen_text) > 45000:
        raise ValueError("Untrusted frozen test contract")
    tree = ast.parse(frozen_text)
    groups = [n for n in tree.body if isinstance(n, ast.ClassDef)
              and n.name == "ProductContract"]
    if len(groups) != 1:
        raise ValueError("Frozen suite needs exactly one ProductContract")
    names = [n.name for n in groups[0].body
             if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    if not names or len(set(names)) != len(names):
        raise ValueError("Duplicate or empty ProductContract")
    return tuple(names)


def validate(manifest, frozen_text):
    """Reject incomplete, cyclic or widened DAG and verify immutable tests."""
    if not isinstance(manifest, Mapping) or set(manifest) != _KEYS:
        raise ValueError("Unknown DAG contract fields")
    if manifest["schema"] != 1 or manifest["approval"] != "host-reviewed":
        raise ValueError("No host-reviewed microtask authorization")
    goal = manifest["goal_id"]
    path = manifest["source_path"]
    function = manifest["function"]
    module = manifest["test_module"]
    if (not isinstance(goal, str) or not _GOAL.fullmatch(goal)
            or not isinstance(path, str) or not _PATH.fullmatch(path)
            or ".." in path.split("/") or path.startswith("/")
            or path.startswith(".") or "\\" in path
            or not isinstance(function, str)
            or len(function.split(".")) > 2
            or any(not p.isidentifier() for p in function.split("."))
            or not isinstance(module, str) or not _TEST.fullmatch(module)
            or manifest["model"] not in ("qwen2.5-coder:7b", "qwen3.5:9b")
            or not isinstance(manifest["frozen_sha256"], str)
            or not _SHA.fullmatch(manifest["frozen_sha256"])
            or digest(frozen_text.encode("utf-8")) != manifest["frozen_sha256"]
            or not isinstance(manifest["budget"], dict)
            or set(manifest["budget"]) != set(_BUDGET)
            or any(type(manifest["budget"][k]) is not type(v)
                   or (v is False and manifest["budget"][k] is not False)
                   or (type(v) is int and not 0 < manifest["budget"][k] <= v)
                   for k, v in _BUDGET.items())):
        raise ValueError("Invalid, stale or unbounded DAG contract")
    controls = manifest["positive_controls"]
    steps = manifest["steps"]
    frozen = set(test_names(frozen_text))
    if (not isinstance(controls, list) or not controls
            or len(set(controls)) != len(controls)
            or any(not isinstance(x, str) or not _TEST.fullmatch(x) for x in controls)
            or not isinstance(steps, list) or not 1 <= len(steps) <= 20):
        raise ValueError("Missing or excessive steps/controls")
    identities = set()
    tests = set(controls)
    for item in steps:
        if (not isinstance(item, dict) or set(item) != _STEP_KEYS
                or not isinstance(item["id"], str) or not _STEP.fullmatch(item["id"])
                or not item["id"].startswith(goal + ".")
                or item["id"] in identities
                or not isinstance(item["depends_on"], list)
                or len(set(item["depends_on"])) != len(item["depends_on"])
                or any(not isinstance(d, str) or not _STEP.fullmatch(d) for d in item["depends_on"])
                or not isinstance(item["target_test"], str)
                or not _TEST.fullmatch(item["target_test"])
                or item["target_test"] in tests
                or not isinstance(item["anchor"], str)
                or not 1 <= len(item["anchor"]) <= 250
                or "\n" in item["anchor"] or "\r" in item["anchor"]
                or not isinstance(item["task"], str)
                or not 1 <= len(item["task"]) <= 480
                or type(item["priority"]) is not int or not 0 <= item["priority"] <= 3):
            raise ValueError("Malformed, repeated or unauthorized DAG step")
        try:
            ast.parse(item["anchor"], mode="eval")
        except SyntaxError as error:
            raise ValueError("Invalid frozen expression anchor") from error
        identities.add(item["id"])
        tests.add(item["target_test"])
    if tests != frozen:
        raise ValueError("Frozen independent test inventory does not match DAG")
    by_id = {s["id"]: s for s in steps}
    for item in steps:
        if any(d not in by_id or d == item["id"] for d in item["depends_on"]):
            raise ValueError("Missing dependency or self dependency")
    seen = set()
    active = set()
    def visit(step_id):
        if step_id in active:
            raise ValueError("Cyclic microtask dependency")
        if step_id in seen:
            return
        active.add(step_id)
        for dependency in by_id[step_id]["depends_on"]:
            visit(dependency)
        active.remove(step_id)
        seen.add(step_id)
    for item in steps:
        visit(item["id"])
    return manifest


def normalize(manifest, outcomes):
    """One complete independently parsed unittest inventory, no omissions."""
    names = set(manifest["positive_controls"]) | {s["target_test"] for s in manifest["steps"]}
    if not isinstance(outcomes, Mapping) or len(outcomes) != len(names):
        raise ValueError("Missing or excessive frozen test observations")
    result = {}
    for name, status in outcomes.items():
        if not isinstance(name, str) or status not in ("ok", "FAIL"):
            raise ValueError("Invalid outcome")
        match = re.fullmatch(r"(test_[A-Za-z0-9_]+) \([^\r\n]+\)", name)
        if not match or match.group(1) in result:
            raise ValueError("Unverifiable or duplicated unittest test identity")
        result[match.group(1)] = status
    if set(result) != names:
        raise ValueError("Wrong frozen product test inventory")
    return result


def dependency_frontier(steps, statuses):
    """Reusable deterministic DAG frontier for approved code *or* roadmap steps.

    A frontier is scheduling advice, never execution permission. Validate all
    IDs, dependencies, cycles and states before returning ready nodes.
    """
    if (not isinstance(steps, (tuple, list)) or not 1 <= len(steps) <= 20
            or not all(isinstance(item, Mapping) for item in steps)):
        raise ValueError("Untrusted microtask graph")
    by_id = {}
    for item in steps:
        key = item.get("id")
        deps = item.get("depends_on")
        priority = item.get("priority")
        if (not isinstance(key, str) or not _STEP.fullmatch(key)
                or key in by_id
                or not isinstance(deps, (tuple, list))
                or len(deps) != len(set(deps))
                or any(not isinstance(dep, str) or not _STEP.fullmatch(dep) for dep in deps)
                or type(priority) is not int or not 0 <= priority <= 3):
            raise ValueError("Malformed microtask graph node")
        by_id[key] = item
    if (not isinstance(statuses, Mapping) or set(statuses) != set(by_id)
            or any(status not in ("pending", "verified") for status in statuses.values())):
        raise ValueError("Untrusted microtask status inventory")
    visiting, seen = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError("Cyclic microtask graph")
        if key in seen:
            return
        visiting.add(key)
        for dep in by_id[key]["depends_on"]:
            if dep not in by_id or dep == key:
                raise ValueError("Missing or self microtask dependency")
            visit(dep)
        visiting.remove(key)
        seen.add(key)
    for key in by_id:
        visit(key)
    frontier = tuple(sorted(
        (item for item in steps
         if statuses[item["id"]] == "pending"
         and all(statuses[dep] == "verified" for dep in item["depends_on"])),
        key=lambda item: (item["priority"], item["id"]),
    ))
    if not frontier and "pending" in statuses.values():
        raise ValueError("Pending DAG nodes have no ready frontier")
    return frontier


def next_ready(manifest, statuses, outcomes):
    """Priority-ordered topological frontier; never let an LLM invent work."""
    parsed = normalize(manifest, outcomes)
    for name in manifest["positive_controls"]:
        if parsed[name] != "ok":
            raise ValueError("Positive control regressed")
    ids = {s["id"] for s in manifest["steps"]}
    if (not isinstance(statuses, Mapping) or set(statuses) != ids
            or any(x not in ("pending", "verified") for x in statuses.values())):
        raise ValueError("Invalid durable DAG state")
    for item in manifest["steps"]:
        if statuses[item["id"]] == "verified" and parsed[item["target_test"]] != "ok":
            raise ValueError("Verified test regressed")
    candidates = [s for s in manifest["steps"]
                  if statuses[s["id"]] == "pending"
                  and all(statuses[d] == "verified" for d in s["depends_on"])]
    if not candidates and any(x == "pending" for x in statuses.values()):
        raise ValueError("No reachable DAG frontier")
    for step in sorted(candidates, key=lambda s:(s["priority"], s["id"])):
        if parsed[step["target_test"]] != "FAIL":
            # A target passing without its own independent qualified step
            # must not silently be declared an accepted DAG node.
            raise ValueError("Step target passed outside reviewed microtask")
        return step
    if all(x == "verified" for x in statuses.values()) and all(x == "ok" for x in parsed.values()):
        return None
    raise ValueError("Incomplete DAG or unverified frozen suite")


def assess(manifest, step, before, after, statuses):
    """Target fixed, regressions forbidden, full suite required after every edit."""
    if step["id"] not in statuses or statuses[step["id"]] != "pending":
        raise ValueError("Wrong active microtask")
    a = normalize(manifest, before)
    b = normalize(manifest, after)
    new_failures = {k for k in b if b[k] == "FAIL" and a[k] == "ok"}
    if new_failures or any(b[k] != "ok" for k in manifest["positive_controls"]):
        return "rejected_regression"
    if a[step["target_test"]] != "FAIL" or b[step["target_test"]] != "ok":
        return "rejected_no_progress"
    if not {k for k in b if b[k] == "FAIL"} < {k for k in a if a[k] == "FAIL"}:
        return "rejected_no_progress"
    return "all_frozen_tests_green" if all(x == "ok" for x in b.values()) else "strict_partial_improvement"

