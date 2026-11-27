"""Generic AST mutation candidates, not an execution or admission engine.

Produce bounded, deterministic expression changes. A trusted caller owns
source approval, independent test cases, execution and equivalence checks.
No model text, source loading, filesystem or network access.
"""
import ast
from copy import deepcopy

def expression_mutants(tree, *, limit=256):
    if not isinstance(tree,ast.Module) or len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):
        raise ValueError("one_function_required")
    if type(limit) is not int or not 1<=limit<=256:raise ValueError("mutation_limit")
    original=list(ast.walk(tree))
    if len(original)>4000:raise ValueError("ast_bound")
    offered=0
    for index,node in enumerate(original):
        # Change only a condition's value, not control-flow structure.
        if isinstance(node,(ast.If,ast.IfExp)):
            test=node.test
            if isinstance(test,ast.Constant) and type(test.value) is bool:continue
            replacement=ast.UnaryOp(op=ast.Not(),operand=deepcopy(test))
            mode="predicate"
        elif isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub)):
            # Restrict to arithmetic with a literal numeric operand; avoid
            # arbitrary changes to list/string concatenations.
            if not any(isinstance(v,ast.Constant) and type(v.value) in (int,float) for v in (node.left,node.right)):continue
            test=node
            replacement=deepcopy(node)
            replacement.op=ast.Sub() if isinstance(node.op,ast.Add) else ast.Add()
            mode="arithmetic"
        else:
            continue
        before=ast.unparse(test)
        after=ast.unparse(replacement)
        if len(before)>900 or len(after)>900:continue
        candidate=deepcopy(tree)
        current=list(ast.walk(candidate))[index]
        replacement=ast.copy_location(replacement,test)
        if mode=="predicate":
            current.test=replacement
        else:
            current.op=replacement.op
        yield candidate,{"kind":mode,"line":test.lineno,"column":test.col_offset,
                         "operator_index":0,"before":before,"after":after}
        offered+=1
        if offered>=limit:return
