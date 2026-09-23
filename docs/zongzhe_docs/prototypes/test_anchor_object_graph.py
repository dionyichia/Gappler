"""Checks for AnchorObjectGraph, plus a reproduction of the failure class
the upstream two-set arrangement is open to.

Stdlib unittest so this can run at bench level L0-L2 with no dependencies.
"""

import unittest
from collections import defaultdict

from anchor_object_graph import AnchorObjectGraph, Sighting


# --------------------------------------------------------------------------
# A minimal stand-in for how HiCo-Nav stores edges: two independent id sets,
# each owned by a different object, each written separately. This is NOT a
# copy of upstream code, it is the arrangement the class diagram describes,
# written out so the failure mode can be demonstrated rather than asserted.
# --------------------------------------------------------------------------
class TwoSetScheme:
    def __init__(self):
        self.anchor_objects = defaultdict(set)   # Keyframe.objects_3d
        self.object_observers = defaultdict(set) # Object3D.observers

    def observe(self, anchor, obj):
        self.anchor_objects[anchor].add(obj)
        self.object_observers[obj].add(anchor)

    def delete_keyframe(self, anchor):
        """Unwinds from the anchor side only, as the class diagram records."""
        self.anchor_objects.pop(anchor, None)

    def merge_objects(self, surviving, absorbed):
        """Object3D.merge unions observers on the surviving node."""
        self.object_observers[surviving] |= self.object_observers[absorbed]
        del self.object_observers[absorbed]


class TwoSetFailureModes(unittest.TestCase):
    """Shows what the arrangement permits. Not a claim about upstream's code."""

    def test_anchor_eviction_leaves_dangling_observer_ids(self):
        g = TwoSetScheme()
        g.observe(anchor=1, obj=100)
        g.observe(anchor=2, obj=100)
        g.delete_keyframe(1)

        self.assertNotIn(1, g.anchor_objects)                 # anchor side clean
        self.assertIn(1, g.object_observers[100])             # object side stale
        # The consequence: degree is now wrong, and degree feeds r_j.
        self.assertEqual(len(g.object_observers[100]), 2)     # says 2
        self.assertEqual(len(g.anchor_objects), 1)            # only 1 anchor left

    def test_inflated_degree_can_make_the_ilp_infeasible(self):
        """r_j = min(kappa, degree) is computed from the stale set."""
        g = TwoSetScheme()
        for anchor in (1, 2, 3):
            g.observe(anchor, obj=100)
        for anchor in (1, 2):
            g.delete_keyframe(anchor)

        kappa = 3
        stale_degree = len(g.object_observers[100])
        r_j = min(kappa, stale_degree)
        live_anchors = len(g.anchor_objects)
        self.assertEqual(r_j, 3)          # demands 3
        self.assertEqual(live_anchors, 1) # only 1 exists -> constraint unsatisfiable

    def test_object_merge_leaves_anchors_pointing_at_the_absorbed_id(self):
        g = TwoSetScheme()
        g.observe(anchor=1, obj=100)
        g.observe(anchor=2, obj=200)
        g.merge_objects(surviving=100, absorbed=200)

        self.assertNotIn(200, g.object_observers)      # object gone
        self.assertIn(200, g.anchor_objects[2])        # anchor still points at it
        self.assertNotIn(100, g.anchor_objects[2])     # and not at its replacement


class GraphStaysConsistent(unittest.TestCase):
    """The same sequences, against the single-source-of-truth structure."""

    def test_anchor_eviction_is_atomic(self):
        g = AnchorObjectGraph()
        g.observe(1, 100)
        g.observe(2, 100)
        g.remove_anchor(1)

        self.assertEqual(g.anchors_of(100), frozenset({2}))
        self.assertEqual(g.degree(100), 1)
        self.assertEqual(g.check_invariants(), [])

    def test_object_merge_rewrites_both_directions(self):
        g = AnchorObjectGraph()
        g.observe(1, 100)
        g.observe(2, 200)
        g.merge_objects(surviving=100, absorbed=200)

        self.assertEqual(g.objects(), frozenset({100}))
        self.assertEqual(g.objects_of(2), frozenset({100}))
        self.assertEqual(g.anchors_of(100), frozenset({1, 2}))
        self.assertEqual(g.check_invariants(), [])

    def test_merge_fuses_colliding_edge_payloads(self):
        g = AnchorObjectGraph()
        g.observe(1, 100, Sighting(detections=2, mask_pixels=500, confidence=0.7))
        g.observe(1, 200, Sighting(detections=3, mask_pixels=900, confidence=0.5))
        g.merge_objects(surviving=100, absorbed=200)

        s = g.sighting(1, 100)
        self.assertEqual(s.detections, 5)      # summed
        self.assertEqual(s.mask_pixels, 900)   # max
        self.assertAlmostEqual(s.confidence, 0.7)
        self.assertEqual(g.check_invariants(), [])

    def test_removing_the_last_anchor_removes_the_object_entry(self):
        g = AnchorObjectGraph()
        g.observe(1, 100)
        g.remove_anchor(1)
        self.assertEqual(g.objects(), frozenset())
        self.assertEqual(g.anchors(), frozenset())
        self.assertEqual(g.check_invariants(), [])

    def test_randomised_operations_never_break_the_invariant(self):
        import random
        rng = random.Random(20260921)
        g = AnchorObjectGraph()
        for step in range(3000):
            roll = rng.random()
            if roll < 0.55:
                g.observe(rng.randrange(40), rng.randrange(25))
            elif roll < 0.75 and g.anchors():
                g.remove_anchor(rng.choice(sorted(g.anchors())))
            elif roll < 0.90 and len(g.objects()) >= 2:
                a, b = rng.sample(sorted(g.objects()), 2)
                g.merge_objects(a, b)
            elif g.objects():
                g.remove_object(rng.choice(sorted(g.objects())))
            if step % 250 == 0:
                self.assertEqual(g.check_invariants(), [], f"broke at step {step}")
        self.assertEqual(g.check_invariants(), [])


class CoverageAndPruning(unittest.TestCase):

    def test_clamp_keeps_every_requirement_satisfiable(self):
        g = AnchorObjectGraph()
        for anchor in (1, 2, 3, 4, 5):
            g.observe(anchor, obj=100)      # sofa, seen 5 times
        g.observe(6, obj=200)               # mug, seen once

        req = g.coverage_requirements(kappa=3)
        self.assertEqual(req[100], 3)       # clamped down from 5
        self.assertEqual(req[200], 1)       # clamped up-to-degree, not 3
        for obj, r in req.items():
            self.assertLessEqual(r, g.degree(obj))   # always satisfiable

    def test_kappa_one_is_set_cover(self):
        g = AnchorObjectGraph()
        for anchor in (1, 2, 3):
            for obj in (100, 200):
                g.observe(anchor, obj)

        kept, evicted = g.prune(kappa=1, apply=False)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(evicted), 2)

    def test_kappa_three_keeps_viewpoint_redundancy(self):
        g = AnchorObjectGraph()
        for anchor in (1, 2, 3):
            for obj in (100, 200):
                g.observe(anchor, obj)

        kept, _ = g.prune(kappa=3, apply=False)
        self.assertEqual(len(kept), 3)

    def test_prune_meets_every_requirement(self):
        import random
        rng = random.Random(7)
        g = AnchorObjectGraph()
        for anchor in range(30):
            for obj in rng.sample(range(20), rng.randrange(1, 6)):
                g.observe(anchor, obj)

        for kappa in (1, 2, 3, 5):
            probe = AnchorObjectGraph()
            for (a, o) in g:
                probe.observe(a, o)
            want = probe.coverage_requirements(kappa)
            kept, _ = probe.prune(kappa=kappa, apply=False)
            for obj, r in want.items():
                got = len(probe.anchors_of(obj) & kept)
                self.assertGreaterEqual(got, r, f"kappa={kappa} object={obj}")

    def test_prune_applies_and_leaves_graph_consistent(self):
        g = AnchorObjectGraph()
        for anchor in range(10):
            g.observe(anchor, obj=100)
        g.prune(kappa=2, apply=True)
        self.assertEqual(g.degree(100), 2)
        self.assertEqual(g.check_invariants(), [])

    def test_cost_steers_which_anchors_survive(self):
        g = AnchorObjectGraph()
        for anchor in (1, 2):
            for obj in (100, 200):
                g.observe(anchor, obj)
        expensive = {1: 10.0, 2: 1.0}
        kept, _ = g.prune(kappa=1, cost=lambda a: expensive[a], apply=False)
        self.assertEqual(kept, {2})


class EdgeAttributes(unittest.TestCase):

    def test_best_anchor_uses_view_quality(self):
        g = AnchorObjectGraph()
        g.observe(1, 100, Sighting(mask_pixels=100, confidence=0.9, occluded_fraction=0.8))
        g.observe(2, 100, Sighting(mask_pixels=900, confidence=0.9, occluded_fraction=0.0))
        g.observe(3, 100, Sighting(mask_pixels=400, confidence=0.5, occluded_fraction=0.1))
        self.assertEqual(g.best_anchor_for(100), 2)

    def test_best_anchor_of_unknown_object_is_none(self):
        self.assertIsNone(AnchorObjectGraph().best_anchor_for(999))


if __name__ == "__main__":
    unittest.main(verbosity=2)
