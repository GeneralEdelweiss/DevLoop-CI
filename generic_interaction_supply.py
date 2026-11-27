"""Generic bounded discovery of distinct higher-order observations.

Only abstract integer paths and case indices are handled here. The caller
owns the independent evaluator; no source, model, network or filesystem.
"""
from itertools import combinations
from functools import lru_cache

def discover_triplets(paths, singles, known, evaluate, case_count, *, max_trials=96):
    if (type(case_count) is not int or not 2<=case_count<=500 or
        type(max_trials) is not int or not 1<=max_trials<=256 or
        len(paths)!=len(singles) or len(paths)>24):
        raise ValueError("invalid_bounds")
    if len(set(paths))!=len(paths) or any(
        not isinstance(p,tuple) or not p or any(type(i) is not int or i<0 for i in p) for p in paths):
        raise ValueError("invalid_paths")
    def checked(values):
        values=tuple(values)
        if any(type(x) is not int or not 0<=x<case_count for x in values) or tuple(sorted(set(values)))!=values:
            raise ValueError("invalid_signature")
        return frozenset(values)
    single=[checked(s) for s in singles]
    seen={checked(s) for s in known}|set(single)
    @lru_cache(maxsize=256)
    def pair(i,j):
        return checked(evaluate((i,j)))
    def disjoint(i,j):
        a,b=paths[i],paths[j]
        size=min(len(a),len(b))
        return a[:size]!=b[:size]
    trials=0
    results=[]
    for group in combinations(range(len(paths)),3):
        if not all(disjoint(i,j) for i,j in combinations(group,2)):
            continue
        if trials>=max_trials:break
        trials+=1
        i,j,k=group
        actual=checked(evaluate(group))
        if not actual or len(actual)==case_count or actual in seen:
            continue
        if actual==single[i]|single[j]|single[k]:
            continue
        partitions=((i,j,k),(i,k,j),(j,k,i))
        lower=[(pair(a,b),single[c]) for a,b,c in partitions]
        # An independently measured lower-order observation or additive
        # combination is not a new higher-order observation.
        if any(actual in (ab,c,ab|c) for ab,c in lower):
            continue
        seen.add(actual)
        results.append((group,tuple(sorted(actual))))
    return results, trials
