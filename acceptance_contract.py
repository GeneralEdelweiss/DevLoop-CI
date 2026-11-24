"""Generic CI assertions for a bounded repair sequence; no product dependencies."""


def pending(inventory, expected, controls):
    if not expected or set(inventory) != set(expected) or set(controls) != set(expected):
        raise ValueError('Incomplete goal inventory')
    result = set()
    for goal, names in expected.items():
        cases = inventory[goal]
        if not names or set(cases) != set(names) or not controls[goal] or not set(controls[goal]) <= set(names):
            raise ValueError('Incomplete test inventory')
        if any(value not in ('ok', 'FAIL') for value in cases.values()):
            raise ValueError('Invalid test verdict')
        if any(cases[name] != 'ok' for name in controls[goal]):
            raise ValueError('Positive control failed')
        if 'FAIL' in cases.values():
            result.add(goal)
    return result


def transition(before, after, expected, controls, goal, stage):
    remaining = pending(before, expected, controls)
    next_remaining = pending(after, expected, controls)
    if goal not in remaining or next_remaining != remaining - {goal}:
        raise ValueError('Repair did not resolve exactly one pending goal')
    if any(before[key] != after[key] for key in expected if key != goal):
        raise ValueError('Unrelated inventory changed')
    required = 'next' if next_remaining else 'exhausted'
    if stage != required:
        raise ValueError('Successor disposition contradicts independent tests')
    return next_remaining


def completion(initial, repaired, final):
    if final or len(repaired) != len(set(repaired)) or set(repaired) != set(initial):
        raise ValueError('Incomplete or duplicate repair evidence')
