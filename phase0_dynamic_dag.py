"""Compile independently qualified dynamic contracts into the existing Eco DAG.

This module accepts host-reviewed dependency edges and exact qualified test
receipts, not model-authored status, executable code or new permissions.
It deliberately never executes, admits or publishes a job. A changed live
Development tip requires fresh qualification instead of replaying old plans.
"""
import re
from collections.abc import Mapping

from phase0_dynamic_contract import _digest
from phase0_generic_dag import dependency_frontier

_SHA = re.compile(r'[a-f0-9]{64}\Z')
_FIELDS = frozenset({'schema', 'kind', 'policy_revision', 'catalog_digest',
                     'dev_revision', 'goal', 'path', 'symbol', 'target',
                     'controls', 'source_sha256', 'test_sha256', 'baseline_sha256',
                     'admission_permitted', 'contract_sha256'})
BUDGET = {'concurrent_model_calls': 1, 'attempts_per_step': 2,
          'num_ctx': 4096, 'num_predict': 900, 'max_prompt_chars': 6500,
          'model_downloads': False}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def compile_dag(catalog, revision, goal, qualified, reviewed_edges,
                *, proven=(), blocked=()):
    """Use independent qualified contracts rather than a hard-coded task list.

    The host must supply freshly qualified contracts and independently reviewed
    edges; a content hash alone is not a provenance or authorization proof.
    """
    binding = catalog.binding(revision)
    _require(goal in catalog.eligible_subtasks(proven_goal_ids=proven,
                                              blocked_goal_ids=blocked),
             'Goal not eligible')
    _require(isinstance(qualified, (list, tuple)) and 1 <= len(qualified) <= 20,
             'Invalid bounded candidate inventory')
    _require(isinstance(reviewed_edges, (list, tuple)) and len(reviewed_edges) <= 190,
             'Invalid reviewed dependencies')
    inventory, seen = {}, set()
    for row in qualified:
        _require(isinstance(row, dict) and set(row) == _FIELDS
                 and type(row['schema']) is int and row['schema'] == 1
                 and row['kind'] == 'existing_regression'
                 and row['admission_permitted'] is False
                 and row['goal'] == goal
                 and all(row[k] == v for k, v in binding.items()),
                 'Invalid or stale qualified contract')
        _require(isinstance(row['path'], str) and row['path'] in catalog.goals[goal]['scope']
                 and all(isinstance(row[k], str) and _SHA.fullmatch(row[k])
                         for k in ('contract_sha256', 'source_sha256', 'test_sha256', 'baseline_sha256'))
                 and isinstance(row['symbol'], str) and isinstance(row['target'], str)
                 and isinstance(row['controls'], list) and bool(row['controls'])
                 and all(isinstance(c, str) for c in row['controls'])
                 and len(set(row['controls'])) == len(row['controls'])
                 and row['target'] not in row['controls'],
                 'Invalid scope, test or digest binding')
        key = row['contract_sha256']
        _require(_digest({k: v for k, v in row.items() if k != 'contract_sha256'}) == key,
                 'Changed qualification')
        identity = (row['path'], row['symbol'], row['target'], row['test_sha256'])
        _require(key not in inventory and identity not in seen, 'Duplicate contract')
        inventory[key] = row
        seen.add(identity)
    rank = catalog.goals[goal]['priority']
    _require(type(rank) is int and 0 <= rank <= 3, 'Invalid goal priority')
    keys = sorted(inventory)
    ids = {key: f'{goal}.{index}' for index, key in enumerate(keys, 1)}
    edges = {key: [] for key in keys}
    for edge in reviewed_edges:
        _require(isinstance(edge, (list, tuple)) and len(edge) == 2
                 and all(isinstance(k, str) and k in inventory for k in edge),
                 'Unknown dependency')
        child, parent = edge
        _require(child != parent and parent not in edges[child], 'Duplicate or self dependency')
        edges[child].append(parent)
    steps = [{'id': ids[key], 'depends_on': sorted(ids[parent] for parent in edges[key]),
              'priority': rank, 'contract_sha256': key,
              'path': inventory[key]['path'], 'symbol': inventory[key]['symbol'],
              'target': inventory[key]['target'],
              'test_sha256': inventory[key]['test_sha256']} for key in keys]
    # Existing generic Eco graph validator rejects cycles and missing nodes.
    dependency_frontier(steps, {step['id']: 'pending' for step in steps})
    result = {'schema': 1, **binding, 'goal': goal, 'steps': steps,
              'budget': dict(BUDGET), 'admission_permitted': False}
    return {**result, 'plan_sha256': _digest(result)}


def ready_step(catalog, revision, plan, qualified, reviewed_edges,
               *, verified, outcomes, proven=(), blocked=()):
    """Select one microstep under the existing Eco frontier.

    Outcomes and verified step IDs must come from the independent runner, not
    an LLM. This is only an isolated microtask frontier at the bound tip.
    A published successor must be planned again against its own current tip.
    """
    _require(isinstance(plan, dict) and isinstance(plan.get('goal'), str),
             'Invalid dynamic plan')
    expected = compile_dag(catalog, revision, plan['goal'], qualified, reviewed_edges,
                           proven=proven, blocked=blocked)
    _require(plan == expected, 'Plan binding changed')
    steps = expected['steps']
    _require(isinstance(verified, (list, tuple)) and
             all(isinstance(v, str) for v in verified) and len(set(verified)) == len(verified)
             and set(verified) <= {step['id'] for step in steps}, 'Invalid completion inventory')
    _require(isinstance(outcomes, Mapping) and set(outcomes) == {s['contract_sha256'] for s in steps},
             'Incomplete independent observations')
    inventory = {row['contract_sha256']: row for row in qualified}
    states = {}
    for step in steps:
        key = step['contract_sha256']
        contract = inventory[key]
        observed = outcomes[key]
        _require(isinstance(observed, Mapping) and set(observed) == {contract['target'], *contract['controls']}
                 and all(observed[c] == 'ok' for c in contract['controls']),
                 'Wrong independent inventory or failed positive control')
        completed = step['id'] in verified
        _require(observed[contract['target']] == ('ok' if completed else 'FAIL'),
                 'Target changed without a qualified step or prior verification regressed')
        states[step['id']] = 'verified' if completed else 'pending'
        if completed:
            _require(set(step['depends_on']) <= set(verified), 'Completed step lacks verified dependency')
    frontier = dependency_frontier(steps, states)
    return frontier[0] if frontier else None
