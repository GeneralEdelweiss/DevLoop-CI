"""Generate bounded independent data-validation cases from declarative rules.

The rule author supplies expected validity, not a call to the function under
test. No application source or runtime is imported by this component.
"""
from copy import deepcopy
import json

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(",",":"))

def build_cases(base, variants, *, limit=500):
    if not isinstance(base,dict) or type(limit) is not int or not 1<=limit<=500:
        raise ValueError("invalid_case_budget")
    if not isinstance(variants,(list,tuple)) or len(variants)>2000:
        raise ValueError("invalid_variants")
    rows=[]
    seen={}
    labels=set()
    def add(label,value,accepted):
        if not isinstance(label,str) or not 1<=len(label)<=120 or label in labels or type(accepted) is not bool:
            raise ValueError("invalid_rule")
        labels.add(label)
        signature=canonical(value)
        if signature in seen:
            if seen[signature]!=accepted:raise ValueError("contradictory_oracles")
            return
        if len(rows)>=limit:raise ValueError("case_budget_exceeded")
        seen[signature]=accepted
        rows.append({"label":label,"args":[deepcopy(value)],"expected":{"value":deepcopy(value)} if accepted else {"error":"ValueError"}})
    add("baseline",base,True)
    for label,patch,accepted in variants:
        if not isinstance(patch,dict) or not patch or not set(patch)<=set(base):
            raise ValueError("invalid_patch")
        obj=deepcopy(base)
        obj.update(deepcopy(patch))
        add(label,obj,accepted)
    return rows
