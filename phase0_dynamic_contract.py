"""Prepare revision-bound regression contracts from independently observed tests.

This is a pure qualification primitive, not an admission or execution path.
Only the trusted host may provide the catalog, scope, reviewed test inventory,
and independently verified baseline. Model proposals are untrusted selectors.
"""
import hashlib
import json
import re
from collections.abc import Mapping

_SHA = re.compile(r'[a-f0-9]{64}\Z')
_SYMBOL = re.compile(r'[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)?\Z')
_TEST = re.compile(r'test_[A-Za-z_0-9]+(?:\.[A-Za-z_][A-Za-z_0-9]*){2}\Z')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def qualify_regression(catalog, revision, proposal, *, approved_symbols,
                       reviewed_tests, baseline, proven=(), blocked=(), occupied=()):
    """Return a data-only candidate for one real red test and green controls.

    The caller must verify the checkout and baseline receipt before calling,
    and independently enforce attempt limits, locks, test execution and admission.
    No proposal can choose a command, test implementation, or new permission.
    """
    binding = catalog.binding(revision)
    _require(isinstance(proposal, dict) and set(proposal) == {'goal', 'path', 'symbol', 'target'},
             'Invalid proposal schema')
    goal, path, symbol, target = (proposal[k] for k in ('goal', 'path', 'symbol', 'target'))
    _require(all(type(v) is str for v in (goal, path, symbol, target)), 'Invalid selector')
    _require(goal in catalog.eligible_subtasks(proven_goal_ids=proven, blocked_goal_ids=blocked),
             'Goal not eligible')
    _require(path in catalog.goals[goal]['scope'] and path in approved_symbols
             and not any(path.casefold() == p.casefold() for p in occupied), 'Scope unavailable')
    _require(_SYMBOL.fullmatch(symbol) and symbol in approved_symbols[path], 'Symbol not approved')
    _require(_TEST.fullmatch(target) and target in reviewed_tests, 'Test not reviewed')
    # Reviewed test inventory is selected from trusted installed policy, not Development/model text.
    review = reviewed_tests[target]
    _require(isinstance(review, Mapping) and set(review) == {'path', 'symbol', 'sha256', 'controls', 'goal_ids'},
             'Invalid reviewed test binding')
    _require(review['path'] == path and review['symbol'] == symbol
             and isinstance(review['sha256'], str) and _SHA.fullmatch(review['sha256']),
             'Test scope mismatch')
    goal_ids = review['goal_ids']
    _require(isinstance(goal_ids, (tuple, list)) and 1 <= len(goal_ids) <= 16
             and all(isinstance(g, str) and g in catalog.goals for g in goal_ids)
             and len(set(goal_ids)) == len(goal_ids) and goal in goal_ids,
             'Test relevance not independently bound')
    controls = review['controls']
    _require(isinstance(controls, (list, tuple)) and 1 <= len(controls) <= 16
             and all(isinstance(c, str) and _TEST.fullmatch(c) for c in controls)
             and len(set(controls)) == len(controls) and target not in controls,
             'Invalid positive controls')
    _require(all(c.split('.')[0] == target.split('.')[0] for c in controls), 'Mixed test modules')
    _require(isinstance(baseline, dict) and set(baseline) == {'binding', 'path', 'symbol', 'source_sha256', 'test_sha256', 'outcomes'},
             'Invalid baseline receipt')
    _require(baseline['binding'] == binding and baseline['path'] == path and baseline['symbol'] == symbol
             and baseline['test_sha256'] == review['sha256']
             and isinstance(baseline['source_sha256'], str) and _SHA.fullmatch(baseline['source_sha256']),
             'Stale baseline')
    outcomes = baseline['outcomes']
    _require(isinstance(outcomes, dict) and set(outcomes) == {target, *controls}
             and outcomes[target] == 'FAIL' and all(outcomes[c] == 'ok' for c in controls),
             'No isolated red baseline with green controls')
    candidate = {'schema': 1, 'kind': 'existing_regression', **binding,
                 'goal': goal, 'path': path, 'symbol': symbol, 'target': target,
                 'controls': sorted(controls), 'source_sha256': baseline['source_sha256'],
                 'test_sha256': review['sha256'], 'baseline_sha256': _digest(baseline),
                 'admission_permitted': False}
    return {**candidate, 'contract_sha256': _digest(candidate)}


def plan_regressions(catalog, revision, *, approved_symbols, reviewed_tests, baselines,
                     proven=(), blocked=(), occupied=()):
    """Derive ranked candidates from trusted review and baseline inventories.

    A test addressing several goals creates only one candidate, for the highest
    ranked eligible goal. Missing or invalid evidence never becomes work.
    The host still owns all runtime admission and retry decisions.
    """
    catalog.binding(revision)
    proven, blocked, occupied = tuple(proven), tuple(blocked), tuple(occupied)
    eligible = catalog.eligible_subtasks(proven_goal_ids=proven, blocked_goal_ids=blocked)
    candidates, rejected = [], []
    _require(isinstance(reviewed_tests, Mapping) and isinstance(baselines, Mapping),
             'Invalid host inventory')
    for target, review in sorted(reviewed_tests.items()):
        if not isinstance(review, Mapping) or not isinstance(review.get('goal_ids'), (tuple, list)):
            raise ValueError('Invalid host review inventory')
        goal = next((g for g in eligible if g in review['goal_ids']), None)
        if goal is None:
            continue
        if target not in baselines:
            rejected.append({'target': target, 'reason': 'baseline_missing'})
            continue
        proposal = {'goal': goal, 'path': review.get('path'),
                    'symbol': review.get('symbol'), 'target': target}
        try:
            candidate = qualify_regression(catalog, revision, proposal, approved_symbols=approved_symbols,
                                           reviewed_tests=reviewed_tests, baseline=baselines[target],
                                           proven=proven, blocked=blocked, occupied=occupied)
        except ValueError:
            rejected.append({'target': target, 'reason': 'qualification_rejected'})
        else:
            candidates.append(candidate)
    candidates.sort(key=lambda c: (eligible.index(c['goal']), c['path'], c['symbol'], c['target']))
    return {'candidates': candidates, 'rejected': rejected}
