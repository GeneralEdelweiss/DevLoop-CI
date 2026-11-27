import unittest
from generic_interaction_supply import discover_triplets

class GenericTests(unittest.TestCase):
    def test_nonadditive_witness_and_duplicate_rejection(self):
        # Three independent boolean flips. A case encodes which flips affect
        # its parity. Odd parity changes the observable result.
        n=8
        paths=[(0,),(1,),(2,)]
        def observe(group):
            return tuple(x for x in range(n) if sum((x>>i)&1 for i in group)%2)
        singles=[observe((i,)) for i in range(3)]
        known=singles+[observe(g) for g in ((0,1),(0,2),(1,2))]
        results,trials=discover_triplets(paths,singles,known,observe,n)
        self.assertEqual(trials,1)
        self.assertEqual(results,[((0,1,2),(1,2,4,7))])
        self.assertEqual(discover_triplets(paths,singles,known+[(1,2,4,7)],observe,n)[0],[])
    def test_overlap_and_additive_rejected(self):
        def observe(group):return tuple(sorted(group))
        self.assertEqual(discover_triplets([(0,),(0,1),(2,)],[(0,),(1,),(2,)],[],observe,4),( [],0))
        self.assertEqual(discover_triplets([(0,),(1,),(2,)],[(0,),(1,),(2,)],[],observe,4),( [],1))
    def test_bounded_and_invalid(self):
        calls=[]
        def observe(g):calls.append(g);return (0,)
        self.assertEqual(discover_triplets([(i,) for i in range(24)],[(0,)]*24,[],observe,4,max_trials=7),( [],7))
        self.assertEqual(len(calls),7)
        with self.assertRaises(ValueError):discover_triplets([(0,),(1,),(2,)],[(0,),(1,),(8,)],[],observe,4)
        with self.assertRaises(ValueError):discover_triplets([(0,)]*3,[(0,)]*3,[],observe,4)
if __name__=="__main__":unittest.main()
