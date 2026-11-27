import ast
import unittest
from generic_expression_supply import expression_mutants
class ExpressionTests(unittest.TestCase):
    def test_exact_changes_and_original_untouched(self):
        tree=ast.parse("def f(x):\n    if x > 0:\n        return x + 1\n    return x - 2\n")
        old=ast.dump(tree)
        variants=list(expression_mutants(tree))
        self.assertEqual(len(variants),3)
        self.assertEqual([m["kind"] for _,m in variants],["predicate","arithmetic","arithmetic"])
        self.assertEqual(ast.dump(tree),old)
        actual=[]
        for candidate,meta in variants:
            env={}
            exec(compile(ast.fix_missing_locations(candidate),"<synthetic>","exec"),env)
            actual.append(tuple(env["f"](x) for x in (-1,0,1)))
        self.assertEqual(actual,[ (0,1,-1),(-3,-2,0),(1,2,2)])
        self.assertEqual(list(expression_mutants(tree,limit=1))[0][1],variants[0][1])
    def test_conditional_expression_and_no_arbitrary_code(self):
        tree=ast.parse("def f(x,y):\n    return x + y if x else y\n")
        variants=list(expression_mutants(tree))
        self.assertEqual(len(variants),1)
        self.assertEqual(variants[0][1]["before"],"x")
        with self.assertRaises(ValueError):list(expression_mutants(ast.parse("x=1")))
        with self.assertRaises(ValueError):list(expression_mutants(tree,limit=True))
if __name__=="__main__":unittest.main()
